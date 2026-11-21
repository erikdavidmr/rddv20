# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class RddPricelistAssignWizard(models.TransientModel):
    _name = 'rdd.pricelist.assign.wizard'
    _description = 'Asistente de Asignación Rápida de Precios'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        compute='_compute_product_info',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        compute='_compute_product_info',
        readonly=True,
    )
    cost_price = fields.Float(
        string='Costo Actual (PUC/Costo)',
        compute='_compute_product_info',
        digits='Product Price',
        readonly=True,
    )
    current_sale_price = fields.Float(
        string='Precio Venta Actual',
        compute='_compute_product_info',
        digits='Product Price',
        readonly=True,
    )

    # Precios a configurar
    regular_price = fields.Float(
        string='Precio Regular / Menudeo ($)',
        digits='Product Price',
        required=True,
        help='Precio normal que aplicará en menudeo (1 unidad o 1 kg).',
    )
    regular_margin = fields.Float(
        string='Margen Regular (%)',
        compute='_compute_margins',
        readonly=True,
    )

    # Mayoreo
    apply_wholesale = fields.Boolean(
        string='¿Asignar Precio Mayoreo?',
        default=True,
        help='Habilita un precio preferencial por volumen.',
    )
    wholesale_price = fields.Float(
        string='Precio Mayoreo ($)',
        digits='Product Price',
    )
    wholesale_min_qty = fields.Float(
        string='Cant. Mínima Mayoreo',
        default=3.0,
        help='Cantidad mínima a partir de la cual aplica el precio de mayoreo.',
    )
    wholesale_margin = fields.Float(
        string='Margen Mayoreo (%)',
        compute='_compute_margins',
        readonly=True,
    )

    # Promoción / Día especial
    apply_promo = fields.Boolean(
        string='¿Asignar Precio Promoción (Miércoles)?',
        default=False,
        help='Habilita una excepción de precio para listas de promoción o días específicos.',
    )
    promo_price = fields.Float(
        string='Precio Promoción ($)',
        digits='Product Price',
    )
    promo_margin = fields.Float(
        string='Margen Promoción (%)',
        compute='_compute_margins',
        readonly=True,
    )
    promo_pricelist_ids = fields.Many2many(
        'product.pricelist',
        'rdd_wizard_promo_pl_rel',
        'wizard_id',
        'pricelist_id',
        string='Listas de Promoción',
        help='Listas especiales donde se registrará el precio de promoción.',
    )

    # Listas Base / Destino
    target_pricelist_ids = fields.Many2many(
        'product.pricelist',
        'rdd_wizard_base_pl_rel',
        'wizard_id',
        'pricelist_id',
        string='Listas Base / Destino',
        required=True,
        help='Listas principales donde se guardarán los precios regulares y de mayoreo.',
    )

    # Visualizador de reglas existentes
    existing_rules_html = fields.Html(
        string='Estado Actual en Listas',
        compute='_compute_existing_rules',
        sanitize=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        product_tmpl_id = res.get('product_tmpl_id')
        if not product_tmpl_id and self._context.get('default_product_tmpl_id'):
            product_tmpl_id = self._context.get('default_product_tmpl_id')
        elif not product_tmpl_id and self._context.get('active_id'):
            product_tmpl_id = self._context.get('active_id')

        if product_tmpl_id:
            tmpl = self.env['product.template'].browse(product_tmpl_id)
            res['product_tmpl_id'] = tmpl.id
            res['regular_price'] = tmpl.list_price or 0.0

            # Buscar listas base recomendadas (Base común, Regular, o multi-company principales)
            base_pls = self.env['product.pricelist'].search([
                '|',
                ('name', 'ilike', 'BASE COMUN'),
                ('name', 'ilike', 'PILOTO - BASE COMUN'),
            ])
            if not base_pls:
                base_pls = self.env['product.pricelist'].search([
                    ('name', 'in', ['PILOTO - BASE COMUN SAN JUAN', 'PILOTO - REGULAR SAN JUAN', 'L1 PDVS'])
                ])
            res['target_pricelist_ids'] = [(6, 0, base_pls.ids)]

            # Buscar listas de promocion (ej. mayoreo san juan o miercoles)
            promo_pls = self.env['product.pricelist'].search([
                ('name', 'ilike', 'PILOTO - MAYOREO SAN JUAN')
            ])
            if not promo_pls:
                promo_pls = self.env['product.pricelist'].search([
                    ('days_apply_m2m.day', 'in', ['miercoles'])
                ])
            res['promo_pricelist_ids'] = [(6, 0, promo_pls.ids)]

        return res

    @api.depends('product_tmpl_id')
    def _compute_product_info(self):
        for rec in self:
            if rec.product_tmpl_id:
                rec.product_uom_id = rec.product_tmpl_id.uom_id
                rec.currency_id = rec.product_tmpl_id.currency_id
                # Si rdd_module tiene puc_field o puc_multicompany, usarlo; sino standard_price
                cost = getattr(rec.product_tmpl_id, 'puc_field', 0.0) or getattr(rec.product_tmpl_id, 'puc_multicompany', 0.0) or rec.product_tmpl_id.standard_price or 0.0
                rec.cost_price = cost
                rec.current_sale_price = rec.product_tmpl_id.list_price or 0.0
            else:
                rec.product_uom_id = False
                rec.currency_id = self.env.company.currency_id
                rec.cost_price = 0.0
                rec.current_sale_price = 0.0

    @api.depends('cost_price', 'regular_price', 'wholesale_price', 'promo_price')
    def _compute_margins(self):
        for rec in self:
            cost = rec.cost_price or 0.0
            # Margen = (Precio - Costo) / Precio * 100
            rec.regular_margin = ((rec.regular_price - cost) / rec.regular_price * 100.0) if rec.regular_price > 0 else 0.0
            rec.wholesale_margin = ((rec.wholesale_price - cost) / rec.wholesale_price * 100.0) if rec.wholesale_price > 0 else 0.0
            rec.promo_margin = ((rec.promo_price - cost) / rec.promo_price * 100.0) if rec.promo_price > 0 else 0.0

    @api.depends('product_tmpl_id')
    def _compute_existing_rules(self):
        for rec in self:
            if not rec.product_tmpl_id:
                rec.existing_rules_html = '<p class="text-muted">Seleccione un producto para ver sus reglas.</p>'
                continue

            variant_ids = rec.product_tmpl_id.product_variant_ids.ids
            items = self.env['product.pricelist.item'].search([
                '|',
                ('product_tmpl_id', '=', rec.product_tmpl_id.id),
                ('product_id', 'in', variant_ids),
            ], order='pricelist_id, min_quantity asc')

            if not items:
                rec.existing_rules_html = """
                <div class="alert alert-warning p-2 mb-2" role="alert">
                    <i class="fa fa-exclamation-triangle"></i> 
                    <strong>Sin reglas registradas:</strong> Este producto aún no tiene precios configurados en ninguna lista de precios.
                </div>
                """
                continue

            rows = []
            for it in items:
                comp = it.compute_price
                if comp == 'fixed':
                    price_str = f"${it.fixed_price:,.2f}"
                elif comp == 'discount':
                    price_str = f"-{it.price_discount}% (Dto)"
                elif comp == 'markup':
                    price_str = f"+{abs(it.price_discount)}% (Margen)"
                else:
                    price_str = comp

                pl_name = it.pricelist_id.name or 'Sin Nombre'
                min_q = f"{it.min_quantity:g} {it.product_uom_id.name or rec.product_uom_id.name or 'u'}"
                dates = ""
                if it.date_start or it.date_end:
                    d_from = str(it.date_start)[:10] if it.date_start else "Inicio"
                    d_to = str(it.date_end)[:10] if it.date_end else "Fin"
                    dates = f"<small class='text-muted'>({d_from} a {d_to})</small>"

                rows.append(f"""
                <tr>
                    <td><strong>{pl_name}</strong></td>
                    <td class="text-center">{min_q}</td>
                    <td class="text-end font-weight-bold text-primary">{price_str}</td>
                    <td class="text-center">{dates or '<span class="badge bg-success">Permanente</span>'}</td>
                </tr>
                """)

            table_html = f"""
            <div class="table-responsive" style="max-height: 200px; overflow-y: auto;">
                <table class="table table-sm table-striped table-bordered mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Lista de Precios</th>
                            <th class="text-center">Cant. Mínima</th>
                            <th class="text-end">Precio / Regla</th>
                            <th class="text-center">Vigencia</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
            """
            rec.existing_rules_html = table_html

    def action_apply_prices(self):
        self.ensure_one()
        if not self.product_tmpl_id:
            raise UserError(_('Por favor seleccione un producto.'))
        if self.regular_price <= 0:
            raise UserError(_('El precio regular debe ser mayor a 0.'))

        PricelistItem = self.env['product.pricelist.item']
        updated_count = 0
        created_count = 0

        # 1. Asignar reglas en Listas Base / Destino
        for pl in self.target_pricelist_ids:
            # Regla Regular (min_quantity <= 1.0 y sin fechas específicas)
            existing_reg = PricelistItem.search([
                ('pricelist_id', '=', pl.id),
                ('product_tmpl_id', '=', self.product_tmpl_id.id),
                ('min_quantity', '<=', 1.0),
                ('date_start', '=', False),
                ('date_end', '=', False),
            ], limit=1)

            if existing_reg:
                existing_reg.write({
                    'compute_price': 'fixed',
                    'fixed_price': self.regular_price,
                    'min_quantity': 1.0,
                })
                updated_count += 1
            else:
                PricelistItem.create({
                    'pricelist_id': pl.id,
                    'product_tmpl_id': self.product_tmpl_id.id,
                    'applied_on': '1_product',
                    'compute_price': 'fixed',
                    'fixed_price': self.regular_price,
                    'min_quantity': 1.0,
                })
                created_count += 1

            # Regla Mayoreo
            if self.apply_wholesale and self.wholesale_price > 0 and self.wholesale_min_qty > 1.0:
                existing_wh = PricelistItem.search([
                    ('pricelist_id', '=', pl.id),
                    ('product_tmpl_id', '=', self.product_tmpl_id.id),
                    ('min_quantity', '=', self.wholesale_min_qty),
                    ('date_start', '=', False),
                    ('date_end', '=', False),
                ], limit=1)

                if existing_wh:
                    existing_wh.write({
                        'compute_price': 'fixed',
                        'fixed_price': self.wholesale_price,
                    })
                    updated_count += 1
                else:
                    PricelistItem.create({
                        'pricelist_id': pl.id,
                        'product_tmpl_id': self.product_tmpl_id.id,
                        'applied_on': '1_product',
                        'compute_price': 'fixed',
                        'fixed_price': self.wholesale_price,
                        'min_quantity': self.wholesale_min_qty,
                    })
                    created_count += 1

        # 2. Asignar reglas en Listas de Promoción (Miércoles / Días especiales)
        if self.apply_promo and self.promo_price > 0:
            for pl in self.promo_pricelist_ids:
                existing_promo = PricelistItem.search([
                    ('pricelist_id', '=', pl.id),
                    ('product_tmpl_id', '=', self.product_tmpl_id.id),
                    ('min_quantity', '<=', 1.0),
                ], limit=1)

                if existing_promo:
                    existing_promo.write({
                        'compute_price': 'fixed',
                        'fixed_price': self.promo_price,
                    })
                    updated_count += 1
                else:
                    PricelistItem.create({
                        'pricelist_id': pl.id,
                        'product_tmpl_id': self.product_tmpl_id.id,
                        'applied_on': '1_product',
                        'compute_price': 'fixed',
                        'fixed_price': self.promo_price,
                        'min_quantity': 1.0,
                    })
                    created_count += 1

        # 3. Actualizar el precio de lista base del producto en la ficha
        self.product_tmpl_id.write({
            'list_price': self.regular_price,
        })

        msg = _(
            "Precios asignados correctamente para %(product)s: %(created)d reglas creadas, %(updated)d reglas actualizadas.",
            product=self.product_tmpl_id.name,
            created=created_count,
            updated=updated_count,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Precios Guardados'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
