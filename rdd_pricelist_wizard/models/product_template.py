# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pricelist_rule_count = fields.Integer(
        string='Listas de Precios',
        compute='_compute_pricelist_rule_count',
    )

    def _compute_pricelist_rule_count(self):
        for template in self:
            variant_ids = template.product_variant_ids.ids
            count = self.env['product.pricelist.item'].search_count([
                '|',
                ('product_tmpl_id', '=', template.id),
                ('product_id', 'in', variant_ids),
            ])
            template.pricelist_rule_count = count

    def action_open_pricelist_assign_wizard(self):
        self.ensure_one()
        return {
            'name': _('Asignar Precios: %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'rdd.pricelist.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
            },
        }
