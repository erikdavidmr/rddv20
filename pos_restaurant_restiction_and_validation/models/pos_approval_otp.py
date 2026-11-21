# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################
import random
import string
import hashlib
from datetime import timedelta
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ACTION_TYPES = [
    ('orderline_deleted', 'Borrado de Línea'),
    ('order_deleted', 'Borrado de Orden'),
    ('session_close', 'Cierre de Sesión'),
]

class PosApprovalOtp(models.Model):
    _name = "pos.approval.otp"
    _description = "Código Temporal de Autorización POS (OTP)"
    _order = "id desc"

    code = fields.Char(string="Código OTP", size=8, required=True, index=True, readonly=True)
    pos_config_id = fields.Many2one("pos.config", string="Punto de Venta", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Compañía", related="pos_config_id.company_id", store=True)
    session_id = fields.Many2one("pos.session", string="Sesión POS", required=True, ondelete="cascade", index=True)
    cashier_id = fields.Many2one("hr.employee", string="Cajero Solicitante")
    manager_id = fields.Many2one("hr.employee", string="Gerente Destinatario")
    recipient_email = fields.Char(string="Correo Notificado")
    action_type = fields.Selection(ACTION_TYPES, string="Acción Solicitada", required=True)
    details = fields.Text(string="Detalle de Operación")
    receipt_number = fields.Char(string="Número de Recibo")
    order_number = fields.Char(string="Número de Orden")
    expiration_date = fields.Datetime(string="Fecha de Expiración", required=True)
    is_used = fields.Boolean(string="Usado", default=False, readonly=True)
    used_date = fields.Datetime(string="Fecha de Uso", readonly=True)

    @api.model
    def action_request_otp(self, vals):
        """
        Genera un código OTP de un solo uso y lo envía por correo electrónico (y/o WhatsApp a futuro).
        vals: {
            'config_id': int,
            'session_id': int,
            'cashier_id': int,
            'action_type': str,
            'details': str,
            'receipt_number': str,
            'order_number': str,
        }
        """
        config_id = vals.get('config_id')
        session_id = vals.get('session_id')
        config = self.env['pos.config'].browse(config_id)
        session = self.env['pos.session'].browse(session_id)

        if not config.exists() or not session.exists():
            return {'success': False, 'message': _("Configuración o sesión POS inválida.")}

        # 1. Determinar el correo destinatario
        recipient_email = False
        manager_emp = config.manager_approval_employee_id
        if config.manager_approval_email:
            recipient_email = config.manager_approval_email.strip()
        elif manager_emp and manager_emp.work_email:
            recipient_email = manager_emp.work_email.strip()
        elif config.company_id.email:
            recipient_email = config.company_id.email.strip()

        if not recipient_email:
            return {
                'success': False,
                'message': _("No hay correo configurado para el gerente en esta sucursal (%s). Configure el correo en los ajustes de Punto de Venta.") % config.name
            }

        # 2. Generar código OTP de 6 dígitos numéricos
        otp_code = ''.join(random.choices(string.digits, k=6))

        validity_minutes = config.otp_validity_minutes or 10
        expiration_date = fields.Datetime.now() + timedelta(minutes=validity_minutes)

        cashier_id = vals.get('cashier_id')
        cashier = self.env['hr.employee'].browse(cashier_id) if cashier_id else False

        # Invalida códigos anteriores no usados para la misma sesión y acción
        self.search([
            ('session_id', '=', session.id),
            ('action_type', '=', vals.get('action_type')),
            ('is_used', '=', False)
        ]).write({'is_used': True})

        # 3. Crear registro OTP
        otp_record = self.create({
            'code': otp_code,
            'pos_config_id': config.id,
            'session_id': session.id,
            'cashier_id': cashier.id if cashier and cashier.exists() else False,
            'manager_id': manager_emp.id if manager_emp and manager_emp.exists() else False,
            'recipient_email': recipient_email,
            'action_type': vals.get('action_type', 'orderline_deleted'),
            'details': vals.get('details', ''),
            'receipt_number': vals.get('receipt_number', ''),
            'order_number': vals.get('order_number', ''),
            'expiration_date': expiration_date,
            'is_used': False,
        })

        # 4. Despachar notificación
        delivery_method = config.otp_delivery_method or 'email'
        if delivery_method in ('email', 'both'):
            template = config.otp_mail_template_id or self.env.ref(
                'pos_restaurant_restiction_and_validation.mail_template_pos_approval_otp',
                raise_if_not_found=False
            )
            if template:
                try:
                    template.send_mail(otp_record.id, force_send=True, email_values={'email_to': recipient_email})
                    _logger.info("OTP POS email sent successfully to %s for config %s", recipient_email, config.name)
                except Exception as e:
                    _logger.error("Error sending OTP email: %s", str(e))
            else:
                _logger.warning("No mail template found for POS OTP.")

        # Futura integración WhatsApp
        if delivery_method in ('whatsapp', 'both'):
            self._send_whatsapp_notification(otp_record, config)

        # Ofuscar correo para privacidad en pantalla: ej. j***@empresa.com
        parts = recipient_email.split('@')
        if len(parts) == 2 and len(parts[0]) > 2:
            obfuscated_email = f"{parts[0][:2]}***@{parts[1]}"
        else:
            obfuscated_email = recipient_email

        return {
            'success': True,
            'email': obfuscated_email,
            'validity_minutes': validity_minutes,
        }

    def _send_whatsapp_notification(self, otp_record, config):
        """
        Punto de extensión para envío de WhatsApp cuando el módulo de WhatsApp esté instalado.
        """
        phone = config.manager_approval_phone or (otp_record.manager_id and otp_record.manager_id.mobile_phone)
        if not phone:
            return
        _logger.info("Preparado para WhatsApp: enviando OTP %s al teléfono %s", otp_record.code, phone)

    @api.model
    def validate_approval(self, config_id, session_id, entered_pin, action_type, details=None, cashier_id=None, receipt_number=None, order_number=None):
        """
        Valida el código ingresado:
        1. Primero busca si es un OTP temporal válido.
        2. Si no es OTP, busca si coincide con el PIN permanente de algún manager.
        """
        pin_str = str(entered_pin).strip()
        now = fields.Datetime.now()

        # 1. Verificar OTP Temporal
        otp = self.search([
            ('pos_config_id', '=', config_id),
            ('session_id', '=', session_id),
            ('code', '=', pin_str),
            ('action_type', '=', action_type),
            ('is_used', '=', False),
            ('expiration_date', '>=', now),
        ], limit=1, order="id desc")

        if otp:
            # Quemar el OTP inmediatamente
            otp.write({
                'is_used': True,
                'used_date': now,
            })

            # Registrar en manager.approval
            manager_emp = otp.manager_id
            self.env['manager.approval'].create({
                'session_id': session_id,
                'cashier': cashier_id or (otp.cashier_id.id if otp.cashier_id else False),
                'manager_approved': manager_emp.id if manager_emp else False,
                'state': action_type,
                'receipt_number': receipt_number or otp.receipt_number,
                'order_number': order_number or otp.order_number,
                'is_otp': True,
                'otp_code': otp.code,
            })

            return {
                'approved': True,
                'is_otp': True,
                'manager_id': manager_emp.id if manager_emp else False,
                'manager_name': manager_emp.name if manager_emp else _("Gerente Remoto (OTP)"),
            }

        # 2. Verificar PIN permanente de Gerente (en caso de que el manager esté presente)
        hashed_pin = hashlib.sha1(pin_str.encode('utf-8')).hexdigest()
        
        # Buscar empleados con rol manager de la misma compañía o global
        managers = self.env['hr.employee'].search([
            ('company_id', 'in', [self.env['pos.config'].browse(config_id).company_id.id, False]),
            '|', ('pin', '=', pin_str), ('pin', '=', hashed_pin)
        ])
        
        for manager in managers:
            # Comprobar si tiene rol manager
            if getattr(manager, '_role', False) == 'manager' or getattr(manager, 'user_has_group', lambda g: False)('point_of_sale.group_pos_manager'):
                self.env['manager.approval'].create({
                    'session_id': session_id,
                    'cashier': cashier_id,
                    'manager_approved': manager.id,
                    'state': action_type,
                    'receipt_number': receipt_number,
                    'order_number': order_number,
                    'is_otp': False,
                    'otp_code': False,
                })
                return {
                    'approved': True,
                    'is_otp': False,
                    'manager_id': manager.id,
                    'manager_name': manager.name,
                }

        return {
            'approved': False,
            'message': _("PIN o Código Temporal incorrecto o expirado."),
        }
