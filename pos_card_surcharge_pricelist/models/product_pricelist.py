# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    is_special_td = fields.Boolean(
        string='Lista Especial TD / Tarjeta',
        default=False,
        index=True,
        help='Marca esta lista de precios como tarifa especial para cobro con tarjeta / terminal (TD). '
             'Permite filtrarla en las configuraciones de TPV, cajas y métodos de pago.'
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        if 'is_special_td' not in fields:
            fields.append('is_special_td')
        return fields
