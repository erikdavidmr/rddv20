# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_card_surcharge = fields.Boolean(
        string='Conmutación Automática Tarifa Tarjeta (+2%)',
        default=True,
        help='Si está activo, al seleccionar un método de pago con tarjeta en la pantalla de cobro se conmutará automáticamente a la lista de precios 2.0.'
    )
    card_pricelist_suffix = fields.Char(
        string='Sufijo de Lista Tarjeta',
        default='2.0',
        help='Sufijo para encontrar la lista espejo con tarjeta (ejemplo: si la lista base es "L1", buscará "L1 2.0").'
    )
    default_card_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista de Tarjeta por Defecto (Fallback)',
        help='Lista de precios a utilizar si la lista base no cuenta con una versión espejo 2.0.'
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields.extend(['enable_card_surcharge', 'card_pricelist_suffix', 'default_card_pricelist_id'])
        return fields
