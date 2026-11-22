# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    apply_card_surcharge = fields.Boolean(
        string='Aplica Tarifa Tarjeta (+2%)',
        default=False,
        help='Si está activo, al seleccionar este método de pago en el TPV se conmutará automáticamente a la tarifa con tarjeta (+2%).'
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        if 'apply_card_surcharge' not in fields:
            fields.append('apply_card_surcharge')
        return fields
