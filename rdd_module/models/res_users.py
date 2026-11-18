from odoo import models, fields, _


class InheritsResUsers(models.Model):
    _inherit = 'res.users'

    user_warehouse = fields.Many2many('stock.warehouse', string="Asignación de almacén")
    