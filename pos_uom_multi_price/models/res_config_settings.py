# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ka_multi_uom = fields.Boolean(related='pos_config_id.ka_multi_uom', readonly=False)
