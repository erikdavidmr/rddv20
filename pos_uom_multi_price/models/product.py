# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    multi_uom_price_ids = fields.One2many('product.multi.uom.price', 'product_id', "UOM price")


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Opcion a borrar
    @api.model
    def _load_pos_self_data_fields(self, config_id):
        params = super()._load_pos_self_data_fields(config_id)
        params += ['multi_uom_price_ids']
        return params

    @api.model
    def _load_pos_data_fields(self, config_id):
        result = super()._load_pos_data_fields(config_id)
        result.append('multi_uom_price_ids')
        return result
