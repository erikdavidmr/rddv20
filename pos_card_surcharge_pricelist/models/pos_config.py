# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_card_surcharge = fields.Boolean(
        string='Conmutación Automática Tarifa Tarjeta (+2%)',
        default=True,
        help='Si está activo, al seleccionar un método de pago con tarjeta en la pantalla de cobro se conmutará automáticamente a la lista de precios 2.0 / Especial TD.'
    )
    card_pricelist_suffix = fields.Char(
        string='Sufijo de Lista Tarjeta',
        default='2.0',
        help='Sufijo para encontrar la lista espejo con tarjeta (ejemplo: si la lista base es "L1", buscará "L1 2.0").'
    )
    default_card_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista Tarjeta / Especial TD',
        domain="[('is_special_td', '=', True), '|', ('company_id', '=', company_id), ('company_id', '=', False)]",
        compute='_compute_default_card_pricelist_id',
        store=True,
        readonly=False,
        help='Lista de precios a utilizar al presionar el botón de tarjeta o como tarifa por defecto para este TPV.'
    )

    @api.depends('company_id.card_pricelist_id')
    def _compute_default_card_pricelist_id(self):
        for config in self:
            if not config.default_card_pricelist_id and config.company_id.card_pricelist_id:
                config.default_card_pricelist_id = config.company_id.card_pricelist_id

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        for f in ['enable_card_surcharge', 'card_pricelist_suffix', 'default_card_pricelist_id']:
            if f not in fields:
                fields.append(f)
        return fields
