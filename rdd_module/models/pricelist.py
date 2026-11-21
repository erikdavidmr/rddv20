# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime,date
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)
#from odoo.exceptions import UserError


class InheritProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    # obsoleto pero no puedo borrarlo
    days_apply = fields.Selection(
        selection=[
            ('lunes', 'Lunes'),
            ('martes', 'Martes'),
            ('miercoles', 'Miércoles'),
            ('jueves', 'Jueves'),
            ('viernes', 'Viernes'),
            ('sabado', 'Sábado'),
            ('domingo', 'Domingo'),
        ],
        string='Día de la Semana',
        
    )
    days_apply_m2m = fields.Many2many('pricelist.dias', string="Dias")

    sales_team = fields.Many2many('crm.team', string="Equipo de ventas")

    expire_date = fields.Datetime('Vigencia')

    def change_pricelist(self):
        for record in self:
            # Compare stored selection keys, not translated labels. The keys are
            # deliberately unaccented (e.g. ``miercoles`` and ``sabado``).
            dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
            hoy = datetime.now()
            nombre_dia = dias_semana[hoy.weekday()]
            for days in record.days_apply_m2m:
                if days.day == nombre_dia and (not record.expire_date or hoy <= record.expire_date):
                    pos = self.env['pos.config'].search([('crm_team_id','in',record.sales_team.ids)])
                    for pp in pos:
                        if record.id in pp.available_pricelist_ids.ids:
                            pp.pricelist_id = record.id
                            record.correo_lista_precio_pos(pos, record.name)

    @api.model
    def cron_change_pricelist_all_companies(self):
        """Run the configured schedule for every pricelist."""
        self.search([]).change_pricelist()
                
    def correo_lista_precio_pos(self, pos_configs, lista):
        _logger.info(f"Iniciar cron")
        partner = self.env['res.partner'].browse(3)
        #pos_configs = self.env['pos.config'].search([('status', '=', 'active')])

        nombre_pos_list = []
        emails_list = []

        for pos in pos_configs:
            #if pos.status == 'active':
            nombre_pos_list.append(pos.name)

            employees = pos.cashier_employee_ids | pos.manager_employee_ids | pos.supervised_employee_ids | pos.restrictive_employee_ids
            emails_list.extend(employees.mapped('work_email'))

        # Agregar el correo del partner si existe
        if partner.email:
            emails_list.append(partner.email)

        # Convertimos todo a strings separados por coma
        nombre_pos = ', '.join(nombre_pos_list)
        emails = ', '.join({e for e in emails_list if e and isinstance(e, str) and e.strip()})
        if not emails:
            _logger.info("No hay correos validos para notificar actualizacion de lista de precios.")
            return

        _logger.info(f"Empleados para POS '{nombre_pos}': {emails}")

        # Construimos el correo
        mail_values = {
            'subject': 'Se ha actualizado la lista de precio',
            'body_html': f"<p>Se actualizo la lista de precios en estas cajas: {nombre_pos} con la lista {lista}.</p>",
            'email_to': emails,  # string separado por comas
            'email_from': self.env.user.email,
        }

        # Enviar el correo
        self.env['mail.mail'].create(mail_values).send()
        
    
    def cron_pos_abierto(self):
        _logger.info(f"Iniciar cron")
        partner = self.env['res.partner'].browse(3)
        open_sessions = self.env['pos.session'].search([('state', '=', 'opened')])
        pos_configs = open_sessions.config_id

        nombre_pos_list = []
        emails_list = []

        for pos in pos_configs:
            nombre_pos_list.append(pos.name)
            employees = pos.cashier_employee_ids | pos.manager_employee_ids | pos.supervised_employee_ids | pos.restrictive_employee_ids
            emails_list.extend(employees.mapped('work_email'))
        if not nombre_pos_list:
            return
        # Agregar el correo del partner si existe
        if partner.email:
            emails_list.append(partner.email)

        # Convertimos todo a strings separados por coma
        nombre_pos = ', '.join(nombre_pos_list)
        emails = ', '.join({e for e in emails_list if e and isinstance(e, str) and e.strip()})
        if not emails:
            _logger.info("No hay correos validos para notificar cajas abiertas.")
            return

        _logger.info(f"Empleados para POS '{nombre_pos}': {emails}")

        # Construimos el correo
        mail_values = {
            'subject': 'Se encontraron con cajas abiertas',
            'body_html': f"<p>Se encontraron las siguientes cajas abiertas: {nombre_pos}.</p>",
            'email_to': emails,  # string separado por comas
            'email_from': self.env.user.email,
        }

        # Enviar el correo
        self.env['mail.mail'].create(mail_values).send()

    def _compute_price_rule(
            self, products, quantity, currency=None, uom=None, date=False, compute_price=True,
            **kwargs
    ):
        """ Low-level method - Mono pricelist, multi products
        Returns: dict{product_id: (price, suitable_rule) for the given pricelist}

        Note: self and self.ensure_one()

        :param products: recordset of products (product.product/product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param currency: record of currency (res.currency)
                         note: currency.ensure_one()
        :param uom: unit of measure (uom.uom record)
            If not specified, prices returned are expressed in product uoms
        :param date: date to use for price computation and currency conversions
        :type date: date or datetime
        :param bool compute_price: whether the price should be computed (default: True)

        :returns: product_id: (price, pricelist_rule)
        :rtype: dict
        """
        self and self.ensure_one()  # self is at most one record

        currency = currency or self.currency_id or self.env.company.currency_id
        currency.ensure_one()

        if not products:
            return {}

        if not date:
            # Used to fetch pricelist rules and currency rates
            date = fields.Datetime.now()

        # Fetch all rules potentially matching specified products/templates/categories and date
        rules = self._get_applicable_rules(products, quantity, date, uom=uom, **kwargs)

        results = {}
        for product in products:
            suitable_rule = self.env['product.pricelist.item']

            product_uom = product.uom_id
            target_uom = uom or product_uom  # If no uom is specified, fall back on the product uom

            # Compute quantity in product uom because pricelist rules are specified
            # w.r.t product default UoM (min_quantity, price_surchage, ...)
            if target_uom != product_uom:
                _logger.info(f"aqui xd  {product_uom} - {target_uom}")
                qty_in_product_uom = target_uom._compute_quantity(
                    quantity, product_uom, raise_if_failure=False
                )
            else:
                _logger.info(f"aqui xd2 {product_uom} - {target_uom}")
                qty_in_product_uom = quantity
            _logger.info(f"aqui xd3 {qty_in_product_uom}")
            _logger.info(f"aqui xd4 {quantity}")
            _logger.info(f"aqui xd4 {uom}")

            for rule in rules:
                if rule._is_applicable_for(product, qty_in_product_uom, uom=product_uom):
                    suitable_rule = rule
                    break

            if compute_price:
                price = suitable_rule._compute_price(
                    product, quantity, target_uom, date=date, currency=currency)
            else:
                # Skip price computation when only the rule is requested.
                price = 0.0
            results[product.id] = (price, suitable_rule.id)

        return results

class InheritProductPricelistitem(models.Model):
    _inherit = 'product.pricelist.item'

    markup_rdd = fields.Float('Markup RDD')

    @api.depends('price_discount', 'markup_rdd')
    def _compute_price_markup(self):
        for item in self:
            # item.price_markup = -item.price_discount
            if item.markup_rdd >= 100:
                item.price_markup = 0.0
            else:
                item.price_markup = (100/(1-(item.markup_rdd/100)))-100

    def _inverse_price_markup(self):
        for item in self:
            item.price_discount = -item.price_markup

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'markup_rdd' in vals:
                markup_rdd = vals['markup_rdd'] or 0.0
                if markup_rdd < 100:
                    markup = (100 / (1 - (markup_rdd / 100))) - 100
                    vals['price_discount'] = -markup
                    vals['price_markup'] = markup
                else:
                    vals['price_discount'] = 0.0
                    vals['price_markup'] = 0.0
        return super(InheritProductPricelistitem, self).create(vals_list)

    def write(self, vals):
        if 'markup_rdd' in vals:
            markup_rdd = vals['markup_rdd'] or 0.0
            if markup_rdd < 100:
                markup = (100 / (1 - (markup_rdd / 100))) - 100
                vals['price_discount'] = -markup
                vals['price_markup'] = markup
            else:
                vals['price_discount'] = 0.0
                vals['price_markup'] = 0.0
        return super(InheritProductPricelistitem, self).write(vals)


    def _compute_base_price(self, product, quantity, uom, date, currency):
        """ Compute the base price for a given rule

        :param product: recordset of product (product.product/product.template)
        :param float qty: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency conversions
        :param currency: currency in which the returned price must be expressed

        :returns: base price, expressed in provided pricelist currency
        :rtype: float
        """
        currency.ensure_one()

        rule_base = self.base or 'list_price'
        if rule_base == 'pricelist' and self.base_pricelist_id:
            price = self.base_pricelist_id._get_product_price(
                product, quantity, currency=self.base_pricelist_id.currency_id, uom=uom, date=date
            )
            src_currency = self.base_pricelist_id.currency_id
        elif rule_base == "standard_price":
            src_currency = product.cost_currency_id
            price = product._price_compute(rule_base, uom=uom, date=date)[product.id]
        else: # list_price
            src_currency = product.currency_id
            price = product._price_compute(rule_base, uom=uom, date=date)[product.id]

        if src_currency != currency:
            price = src_currency._convert(price, currency, self.env.company, date, round=False)

        return price

class DiasConfig(models.Model):
    _name = 'pricelist.dias'
    _description = 'Días de aplicación de listas de precios'
    _rec_name = 'nombre'

    nombre = fields.Char('Nombre')

    day = fields.Selection(
        selection=[
            ('lunes', 'Lunes'),
            ('martes', 'Martes'),
            ('miercoles', 'Miércoles'),
            ('jueves', 'Jueves'),
            ('viernes', 'Viernes'),
            ('sabado', 'Sábado'),
            ('domingo', 'Domingo'),
        ],
        string='Día de la Semana',
        
    )
