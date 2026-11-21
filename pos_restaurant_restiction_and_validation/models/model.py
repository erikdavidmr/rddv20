# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################
from odoo import fields, models, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_pos_restaurant_restiction = fields.Boolean("Restaurant Restriction", default=True)
    enable_restriction_on_orderline_delete = fields.Boolean("Enable Restriction on Orderline Delete", default=True)
    enable_restriction_on_order_delete = fields.Boolean("Enable Restriction on Order Delete", default=True)
    enable_restriction_on_session_close = fields.Boolean("Enable Restriction on Session Close", default=True)

    # Configuración de Código Temporal (OTP)
    otp_delivery_method = fields.Selection([
        ('email', 'Correo Electrónico'),
        ('whatsapp', 'WhatsApp (Futuro)'),
        ('both', 'Ambos (Email + WhatsApp)')
    ], string="Método de Notificación OTP", default="email")
    manager_approval_email = fields.Char(string="Correo Notificación Gerente", help="Correo electrónico donde se enviarán los códigos OTP de autorización")
    manager_approval_employee_id = fields.Many2one("hr.employee", string="Gerente Asignado", domain="[('company_id', 'in', [company_id, False])]")
    manager_approval_phone = fields.Char(string="Teléfono WhatsApp Gerente", help="Teléfono móvil con lada del gerente")
    otp_validity_minutes = fields.Integer(string="Vigencia OTP (Minutos)", default=10)
    otp_mail_template_id = fields.Many2one("mail.template", string="Plantilla de Correo OTP", domain="[('model', '=', 'pos.approval.otp')]")
    otp_whatsapp_template_id = fields.Many2one("mail.template", string="Plantilla WhatsApp OTP")

    @api.model
    def _load_pos_data_fields(self, config):
        loaded_fields = super()._load_pos_data_fields(config)
        extra_fields = [
            "enable_pos_restaurant_restiction",
            "enable_restriction_on_orderline_delete",
            "enable_restriction_on_order_delete",
            "enable_restriction_on_session_close",
            "otp_delivery_method",
            "manager_approval_email",
            "otp_validity_minutes",
        ]
        for f in extra_fields:
            if f not in loaded_fields:
                loaded_fields.append(f)
        return loaded_fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_pos_restaurant_restiction = fields.Boolean(related="pos_config_id.enable_pos_restaurant_restiction", readonly=False)
    is_restriction_on_orderline_delete = fields.Boolean(related="pos_config_id.enable_restriction_on_orderline_delete", readonly=False)
    is_restriction_on_order_delete = fields.Boolean(related="pos_config_id.enable_restriction_on_order_delete", readonly=False)
    is_restriction_on_session_close = fields.Boolean(related="pos_config_id.enable_restriction_on_session_close", readonly=False)

    pos_otp_delivery_method = fields.Selection(related="pos_config_id.otp_delivery_method", readonly=False)
    pos_manager_approval_email = fields.Char(related="pos_config_id.manager_approval_email", readonly=False)
    pos_manager_approval_employee_id = fields.Many2one(related="pos_config_id.manager_approval_employee_id", readonly=False)
    pos_manager_approval_phone = fields.Char(related="pos_config_id.manager_approval_phone", readonly=False)
    pos_otp_validity_minutes = fields.Integer(related="pos_config_id.otp_validity_minutes", readonly=False)
    pos_otp_mail_template_id = fields.Many2one(related="pos_config_id.otp_mail_template_id", readonly=False)
    pos_otp_whatsapp_template_id = fields.Many2one(related="pos_config_id.otp_whatsapp_template_id", readonly=False)
