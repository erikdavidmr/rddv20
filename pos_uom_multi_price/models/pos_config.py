# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    ka_multi_uom = fields.Boolean(string="Multi Price UOM")
