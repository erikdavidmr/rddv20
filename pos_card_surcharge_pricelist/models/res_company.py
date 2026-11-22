# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    card_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Tarifa Tarjeta TD por Defecto',
        domain="[('is_special_td', '=', True), '|', ('company_id', '=', id), ('company_id', '=', False)]",
        help='Lista de precios para cobro con tarjeta por defecto para todos los TPV de esta compañía.'
    )
