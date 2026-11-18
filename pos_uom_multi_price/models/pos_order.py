# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import float_is_zero


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_tax_base_line_values(self):
        res = super()._prepare_tax_base_line_values()
        for ol in res:
            ol['uom_id'] = ol['record'].uom_id
        return res

    def _get_fields_for_order_line(self):
        fields = super(PosOrder, self)._get_fields_for_order_line()
        fields.extend(['uom_id'])
        return fields


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    uom_id = fields.Many2one('uom.uom', string="UOM")

    def _is_not_sellable_line(self):
        return super().is_not_sellable_line() or self.uom_id

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['uom_id']
        return params
