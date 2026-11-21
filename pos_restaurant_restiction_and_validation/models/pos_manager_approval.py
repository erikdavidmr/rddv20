# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################
from odoo import api, fields, models

STATES = [
    ('orderline_deleted','Orderline Deleted'),
    ('order_deleted','Order Deleted'),
    ('session_close','Session Close')
]

class ManagerApproval(models.Model):
    _name = "manager.approval"
    _description = "Manager Approval in restaurants"
    _order = 'id desc'

    session_id = fields.Many2one('pos.session', string='Session', required=True, index=True, domain="[('state', '=', 'opened')]")
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='session_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    receipt_number = fields.Char(string='Receipt Number')
    manager_approved = fields.Many2one('hr.employee', string='Manager Approved', readonly=True)
    cashier = fields.Many2one('hr.employee', string='Cashier', readonly=True)
    manager_name = fields.Char(string='Gerente Aprobador', compute='_compute_employee_names', store=True)
    cashier_name = fields.Char(string='Cajero', compute='_compute_employee_names', store=True)
    state = fields.Selection(STATES, string="Action")
    order_number = fields.Char(string='Order Number')
    is_otp = fields.Boolean(string="Autorizado por OTP", default=False, readonly=True)
    otp_code = fields.Char(string="Código OTP", readonly=True)

    @api.depends('manager_approved', 'cashier')
    def _compute_employee_names(self):
        for rec in self:
            rec.manager_name = rec.sudo().manager_approved.name or ''
            rec.cashier_name = rec.sudo().cashier.name or ''

    @api.model
    def getting_all_data(self,kwargs):
        if(kwargs.get('state') == 'session_close'):
            new = 'session_close'
        elif(kwargs.get('state') == 'order_deleted'):
            new = 'order_deleted'
        else:
            new = 'orderline_deleted'
        return self.env['manager.approval'].create({
            'session_id': kwargs.get('session_id'),
            'cashier': kwargs.get('cashier1'),
            'manager_approved': kwargs.get('manager'),
            'state': new,
            'receipt_number': kwargs.get('receipt'),
            'order_number': kwargs.get('order_num'),
            'is_otp': kwargs.get('is_otp', False),
            'otp_code': kwargs.get('otp_code', False),
        })
