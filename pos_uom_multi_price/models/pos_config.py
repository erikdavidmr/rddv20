# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    ka_multi_uom = fields.Boolean(string="Multi Price UOM")

    @api.model
    def _load_pos_data_fields(self, config):
        fields_to_load = super()._load_pos_data_fields(config)
        fields_to_load.append('ka_multi_uom')
        return fields_to_load
