# -*- coding: utf-8 -*-
from odoo import api, fields, models
import re


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def search_price_calculator_products(self, query=None, pricelist_id=None, config_id=None, limit=15):
        """
        Búsqueda optimizada para la Calculadora / Buscador del Punto de Venta.
        Retorna productos coincidentes con precios calculados con impuestos (IVA/IEPS),
        desglose de peso rápido para granel y presentaciones hermanas/relacionadas.
        """
        domain = [
            ('available_in_pos', '=', True),
            ('sale_ok', '=', True),
        ]
        
        query = (query or '').strip()
        if query:
            domain += [
                '|', '|',
                ('barcode', 'ilike', query),
                ('default_code', 'ilike', query),
                ('name', 'ilike', query),
            ]

        pricelist = self.env['product.pricelist'].browse(pricelist_id) if pricelist_id else None
        currency = pricelist.currency_id if pricelist else self.env.company.currency_id

        products = self.search(domain, limit=limit)
        
        # Si la consulta coincide exactamente con un código de barras o código interno, priorizarlo primero
        if query:
            exact = products.filtered(lambda p: (p.barcode and p.barcode == query) or (p.default_code and p.default_code.lower() == query.lower()))
            if exact:
                products = exact + (products - exact)

        results = []
        for p in products:
            results.append(self._get_price_calculator_info(p, pricelist, currency))

        return results

    @api.model
    def get_price_calculator_product_by_id(self, product_id, pricelist_id=None):
        """Retorna el detalle completo de un producto específico."""
        p = self.browse(product_id)
        if not p.exists():
            return None
        pricelist = self.env['product.pricelist'].browse(pricelist_id) if pricelist_id else None
        currency = pricelist.currency_id if pricelist else self.env.company.currency_id
        return self._get_price_calculator_info(p, pricelist, currency)

    @api.model
    def _is_weight_product(self, p):
        uom_name = (p.uom_id.name or '').lower()
        prod_name = (p.name or '').lower()
        return p.to_weight or any(w in uom_name for w in ['kg', 'kilo', 'gram', 'gr', 'g ']) or 'granel' in prod_name

    @api.model
    def _get_price_calculator_info(self, p, pricelist=None, currency=None):
        if not currency:
            currency = self.env.company.currency_id

        price_unit = p.lst_price
        if pricelist:
            price_unit = pricelist._get_product_price(p, 1.0)

        taxes = p.taxes_id
        res_unit = taxes.compute_all(price_unit, currency, 1.0, product=p)
        price_incl = res_unit.get('total_included', price_unit)
        price_excl = res_unit.get('total_excluded', price_unit)

        is_weight = self._is_weight_product(p)

        # Desglose rápido para productos a granel / por peso
        quick_weights = []
        if is_weight and price_incl > 0:
            for g, label in [(100, "100g"), (250, "250g"), (500, "500g"), (1000, "1kg")]:
                qty = g / 1000.0
                calc = taxes.compute_all(price_unit, currency, qty, product=p)
                quick_weights.append({
                    'grams': g,
                    'qty': qty,
                    'label': label,
                    'price': round(calc.get('total_included', price_incl * qty), 2),
                })

        # Búsqueda de presentaciones hermanas (mismo producto en Granel, Paquete, Caja, Pieza, etc.)
        stop_words = {
            'granel', 'gnl', 'paq', 'paquete', 'caja', 'cja', 'pza', 'pieza',
            'pzs', 'piezas', 'kg', 'kilo', 'gr', 'gramos', 'piloto', 'empaque',
            'chico', 'grande', 'display', 'bolsa', 'tira', 'bote', 'tubo'
        }
        clean_name = re.sub(
            r'(?i)\b(\w+)\b',
            lambda m: '' if m.group(1).lower() in stop_words or m.group(1).isdigit() or m.group(1).lower().startswith('c/') else m.group(1),
            p.name or ''
        )
        clean_name = ' '.join(clean_name.split())
        words = [w for w in clean_name.split() if len(w) > 2]
        siblings = []
        if words:
            s_domain = [
                ('id', '!=', p.id),
                ('available_in_pos', '=', True),
                ('sale_ok', '=', True),
            ]
            for w in words[:2]:
                s_domain.append(('name', 'ilike', w))
            sibling_prods = self.search(s_domain, limit=6)
            for s in sibling_prods:
                s_unit = s.lst_price
                if pricelist:
                    s_unit = pricelist._get_product_price(s, 1.0)
                s_calc = s.taxes_id.compute_all(s_unit, currency, 1.0, product=s)
                siblings.append({
                    'id': s.id,
                    'name': s.name,
                    'display_name': s.display_name,
                    'default_code': s.default_code or '',
                    'uom_name': s.uom_id.name or '',
                    'price_incl': round(s_calc.get('total_included', s_unit), 2),
                    'is_weight': self._is_weight_product(s),
                })

        return {
            'id': p.id,
            'name': p.name,
            'display_name': p.display_name,
            'default_code': p.default_code or '',
            'barcode': p.barcode or '',
            'uom_id': p.uom_id.id,
            'uom_name': p.uom_id.name or '',
            'to_weight': p.to_weight,
            'is_weight': is_weight,
            'price_unit': round(price_unit, 2),
            'price_incl': round(price_incl, 2),
            'price_excl': round(price_excl, 2),
            'quick_weights': quick_weights,
            'siblings': siblings,
        }
