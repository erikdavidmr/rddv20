# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    apply_card_surcharge = fields.Boolean(
        string='Aplica Tarifa Tarjeta (+2%)',
        default=False,
        help='Si está activo, al seleccionar este método de pago en el TPV se conmutará automáticamente a la tarifa con tarjeta (+2%).'
    )
    card_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Tarifa Tarjeta Específica',
        domain="[('is_special_td', '=', True), '|', ('company_id', '=', company_id), ('company_id', '=', False)]",
        help='Si se especifica, al pagar con este método en el TPV se activará exactamente esta lista de precios. '
             'Si se deja vacío, utilizará la tarifa espejo 2.0 o la configurada en la caja/compañía.'
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        for f in ['apply_card_surcharge', 'card_pricelist_id']:
            if f not in fields:
                fields.append(f)
        return fields
