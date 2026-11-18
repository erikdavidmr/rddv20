# -*- coding: utf-8 -*-

from odoo import fields, models
#from odoo.exceptions import UserError


class InheritPosConfig(models.Model):
    _inherit = 'pos.config'

    prefix = fields.Char('Prefijo')
    suffix = fields.Char('Sufijo')
    
    def _get_default_params(self):
        params = super()._get_default_params()
        if 'puc_multicompany' not in params['product_product']['fields']:
            params['product_product']['fields'].append('puc_multicompany')
        return params
    
    #rec.consecutive = self.env['ir.sequence'].next_by_code('rdd_module.consecutive.empresarial')

