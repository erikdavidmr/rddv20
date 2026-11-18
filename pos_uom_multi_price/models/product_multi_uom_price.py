# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MultiUom(models.Model):
    _name = 'product.multi.uom.price'
    _inherit = ['pos.load.mixin']
    _description = 'Product multiple uom price'

    product_id = fields.Many2one('product.template',
        string='Product',
        required=True,
        readonly=True)
    currency_id = fields.Many2one(related='product_id.currency_id')
    name = fields.Char(string="Descripción")
    barcode = fields.Char(string="Cód. barras")
    sequence = fields.Integer('Secuencia', default=1)
    uom_id = fields.Many2one('uom.uom', 
        string="Unit of Measure", 
        required=True)
    price = fields.Float('Price',
        digits='Product Price', compute="compute_product_price", store=True)

    _constraint_product_multi_uom_price_uniq = models.Constraint(
        'UNIQUE (product_id,uom_id)',
        'The product and unit of measure combination must be unique.',
    )

    @api.depends('product_id.list_price', 'uom_id')
    def compute_product_price(self):
        for record in self:
            # Odoo 20 stores the conversion to the reference UoM in ``factor``.
            # ``factor_inv`` was removed with the old UoM category model.
            factor = record.uom_id.factor or 1.0
            record.price = round(record.product_id.list_price * factor, 2) or 0



    @api.model
    def _load_pos_data_fields(self, config_id):
        return ['id', 'product_id', 'currency_id', 'sequence', 'uom_id', 'price']
