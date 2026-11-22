# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
import pytz
import logging
_logger = logging.getLogger(__name__)


class InheritProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    # obsoleto pero no puedo borrarlo
    days_apply = fields.Selection(
        selection=[
            ('lunes', 'Lunes'),
            ('martes', 'Martes'),
            ('miercoles', 'Miércoles'),
            ('jueves', 'Jueves'),
            ('viernes', 'Viernes'),
            ('sabado', 'Sábado'),
            ('domingo', 'Domingo'),
        ],
        string='Día de la Semana',
    )
    days_apply_m2m = fields.Many2many('pricelist.dias', string="Dias")

    sales_team = fields.Many2many('crm.team', string="Equipo de ventas")

    expire_date = fields.Datetime('Vigencia')

    use_time_schedule = fields.Boolean(
        string='Restringir por Horario / Turno',
        default=False,
        help='Si se activa, esta lista solo se aplicará dentro de la franja horaria configurada.'
    )
    hour_from = fields.Float(
        string='Hora Inicio',
        default=0.0,
        help='Hora de inicio en formato decimal (ej: 8.5 para 08:30)'
    )
    hour_to = fields.Float(
        string='Hora Fin',
        default=24.0,
        help='Hora fin en formato decimal (ej: 14.0 para 14:00)'
    )
    schedule_priority = fields.Integer(
        string='Prioridad de Turno',
        default=10,
        help='Prioridad cuando varias listas coinciden para el mismo día y horario (mayor número = mayor prioridad)'
    )
    notify_on_change = fields.Boolean(
        string='Notificar Cambio de Tarifa',
        default=True,
        help='Enviar notificación por correo cuando se active esta lista en una caja'
    )
    notification_emails = fields.Char(
        string='Correos de Notificación',
        help='Direcciones de correo separadas por coma para recibir avisos de cambio de tarifa'
    )
    notify_pos_managers = fields.Boolean(
        string='Notificar Personal de TPV',
        default=True,
        help='Incluir correos de cajeros/encargados asignados al Punto de Venta'
    )

    def change_pricelist(self):
        """Evaluate schedule and update pricelist for POS configurations matching these pricelists."""
        target_pls = self if self else self.search([('active', '=', True)])
        if not target_pls:
            return

        domain = []
        if self:
            domain = ['|', ('available_pricelist_ids', 'in', target_pls.ids), ('crm_team_id', 'in', target_pls.mapped('sales_team').ids)]
        pos_configs = self.env['pos.config'].search(domain)

        for pos in pos_configs:
            self._evaluate_pos_pricelist(pos)

    @api.model
    def cron_change_pricelist_all_companies(self):
        """Run the configured schedule for all active POS configurations."""
        pos_configs = self.env['pos.config'].search([])
        for pos in pos_configs:
            self._evaluate_pos_pricelist(pos)

    def _evaluate_pos_pricelist(self, pos):
        """
        Evaluates the best pricelist for a given pos.config based on day, time, and team.
        """
        try:
            return self._evaluate_pos_pricelist_core(pos)
        except Exception as exc:
            _logger.exception("Error al evaluar lista de precios en POS '%s': %s", getattr(pos, 'name', 'TPV'), exc)
            self._handle_pricelist_issue(
                pos,
                issue_type='exception',
                details=f"Error inesperado: {str(exc)}"
            )
            return None

    def _evaluate_pos_pricelist_core(self, pos):
        company = getattr(pos, 'company_id', None)
        tz_name = getattr(company, 'tz', None) or getattr(self.env.user, 'tz', None) or 'America/Mexico_City'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone('America/Mexico_City')

        hoy = datetime.now()
        if hasattr(tz, 'localize') and hoy.tzinfo is None:
            try:
                now_local = pytz.utc.localize(hoy).astimezone(tz)
            except Exception:
                now_local = hoy
        else:
            now_local = hoy

        dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
        nombre_dia = dias_semana[now_local.weekday()]
        current_hour = now_local.hour + (now_local.minute / 60.0) + (now_local.second / 3600.0)

        # Get available pricelists for this pos
        available_pls = getattr(pos, 'available_pricelist_ids', self.env['product.pricelist'])
        if not available_pls:
            self._handle_pricelist_issue(
                pos,
                issue_type='no_candidate',
                details="La caja no tiene ninguna lista de precios asignada en 'available_pricelist_ids'."
            )
            return None

        candidates = []
        for pl in available_pls:
            if hasattr(pl, 'active') and not pl.active:
                continue
            if getattr(pl, 'is_special_td', False):
                continue
            if pl.expire_date and hoy > pl.expire_date:
                continue

            # Check sales_team
            pos_team = getattr(pos, 'crm_team_id', None)
            if pl.sales_team and pos_team and pos_team.id not in pl.sales_team.ids:
                continue

            # Check days
            if pl.days_apply_m2m:
                pl_days = [d.day for d in pl.days_apply_m2m if d.day]
                if nombre_dia not in pl_days:
                    continue

            # Check time schedule
            if pl.use_time_schedule:
                h_from = pl.hour_from or 0.0
                h_to = pl.hour_to or 24.0
                if h_from <= h_to:
                    if not (h_from <= current_hour < h_to):
                        continue
                else:
                    if not (current_hour >= h_from or current_hour < h_to):
                        continue

            candidates.append(pl)

        if not candidates:
            self._handle_pricelist_issue(
                pos,
                issue_type='no_candidate',
                details=f"No se encontró ninguna tarifa configurada para el día '{nombre_dia}' y hora local {current_hour:.2f}h."
            )
            return None

        # Sort candidate pricelists:
        # 1. use_time_schedule (True comes before False)
        # 2. schedule_priority (higher first)
        # 3. ID (descending for latest)
        candidates.sort(
            key=lambda p: (1 if p.use_time_schedule else 0, p.schedule_priority, p.id),
            reverse=True
        )
        best_pl = candidates[0]

        # Idempotency
        current_pl_id = getattr(pos.pricelist_id, 'id', pos.pricelist_id)
        if current_pl_id == best_pl.id:
            return None

        old_pl = pos.pricelist_id
        pos.pricelist_id = best_pl.id

        _logger.info(
            "POS '%s' [%s]: Tarifa actualizada de '%s' -> '%s' (Día: %s, Hora local: %.2fh)",
            getattr(pos, 'name', 'TPV'),
            getattr(company, 'name', 'N/A'),
            getattr(old_pl, 'name', 'N/A') if old_pl else 'N/A',
            best_pl.name,
            nombre_dia,
            current_hour
        )

        # Notify bus if available
        if hasattr(pos, '_notify'):
            try:
                pos._notify('PRICELIST_CHANGED', {
                    'pricelist_id': best_pl.id,
                    'pricelist_name': best_pl.name,
                })
            except Exception as bus_err:
                _logger.debug("No se pudo enviar bus notification para POS %s: %s", getattr(pos, 'name', 'TPV'), bus_err)

        # Auto-resolve pending 'no_candidate' issues for this POS if any
        pos_id = getattr(pos, 'id', None)
        if pos_id:
            pending_issues = self.env['rdd.pricelist.issue'].search([
                ('pos_config_id', '=', pos_id),
                ('issue_type', '=', 'no_candidate'),
                ('state', '=', 'pending'),
            ])
            if pending_issues:
                pending_issues.write({
                    'state': 'resolved',
                    'resolved_by': self.env.user.id if self.env.user else False,
                    'resolved_date': fields.Datetime.now(),
                    'resolution_notes': f"Resuelto automáticamente al entrar en vigencia la lista '{best_pl.name}'.",
                })

        return best_pl

    def _handle_pricelist_issue(self, pos, issue_type='no_candidate', details=''):
        pos_id = getattr(pos, 'id', None)
        if not pos_id:
            return None

        pos_name = getattr(pos, 'name', 'TPV')
        current_pl = getattr(pos, 'pricelist_id', None)
        current_pl_name = getattr(current_pl, 'name', 'Sin tarifa activa')

        # Check if already registered today to avoid spamming every 15 minutes
        today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        existing_issue = self.env['rdd.pricelist.issue'].search([
            ('pos_config_id', '=', pos_id),
            ('issue_type', '=', issue_type),
            ('state', '=', 'pending'),
            ('date', '>=', today_start),
        ], limit=1)

        if existing_issue:
            return existing_issue

        title = f"[{pos_name}] Sin tarifa para horario actual" if issue_type == 'no_candidate' else f"[{pos_name}] Error en cambio de tarifa"
        issue = self.env['rdd.pricelist.issue'].create({
            'name': title,
            'pos_config_id': pos_id,
            'current_pricelist_id': getattr(current_pl, 'id', False),
            'issue_type': issue_type,
            'details': details,
            'state': 'pending',
        })

        _logger.warning("Incidencia registrada para POS '%s': %s", pos_name, title)
        self._send_critical_issue_email(pos, issue, current_pl_name, details)
        return issue

    def _send_critical_issue_email(self, pos, issue, current_pl_name, details):
        pos_name = getattr(pos, 'name', 'TPV')
        company = getattr(pos, 'company_id', None)
        comp_name = getattr(company, 'name', 'RDD')

        emails_list = []
        employees = (
            getattr(pos, 'cashier_employee_ids', self.env['hr.employee']) |
            getattr(pos, 'manager_employee_ids', self.env['hr.employee']) |
            getattr(pos, 'supervised_employee_ids', self.env['hr.employee']) |
            getattr(pos, 'restrictive_employee_ids', self.env['hr.employee'])
        )
        for emp_email in employees.mapped('work_email'):
            if emp_email and emp_email.strip() and '@' in emp_email:
                emails_list.append(emp_email.strip())

        if company and getattr(company, 'email', False):
            emails_list.append(company.email.strip())

        for pl in getattr(pos, 'available_pricelist_ids', []):
            if getattr(pl, 'notification_emails', False):
                for em in pl.notification_emails.split(','):
                    em = em.strip()
                    if em and '@' in em:
                        emails_list.append(em)

        emails_set = sorted(list({e for e in emails_list if e and '@' in e}))
        if not emails_set:
            _logger.info("Sin correos configurados para notificar incidencia en POS '%s'", pos_name)
            return

        recipients_str = ', '.join(emails_set)
        fecha_str = fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; border: 2px solid #d9534f; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #d9534f; color: #ffffff; padding: 18px 24px; text-align: center;">
                <h2 style="margin: 0; font-size: 20px;">🚨 ALERTA: No se pudo cambiar lista de precios en TPV</h2>
            </div>
            <div style="padding: 24px; background-color: #fafafa;">
                <p style="font-size: 15px; color: #333333; margin-top: 0;">
                    El sistema de cambio dinámico de tarifas no pudo aplicar ninguna tarifa para la siguiente caja:
                </p>
                <table style="width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px;">
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555; width: 35%;">Sucursal / Empresa:</td>
                        <td style="padding: 12px 16px; color: #222;">{comp_name}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555;">Caja / TPV:</td>
                        <td style="padding: 12px 16px; color: #222;">{pos_name}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555;">Fecha y Hora:</td>
                        <td style="padding: 12px 16px; color: #222;">{fecha_str}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555;">Tarifa que se mantuvo activa:</td>
                        <td style="padding: 12px 16px; color: #c9302c; font-weight: bold;">{current_pl_name}</td>
                    </tr>
                    <tr style="background-color: #fdf7f7;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #a94442;">Motivo / Detalle:</td>
                        <td style="padding: 12px 16px; color: #a94442;">{details}</td>
                    </tr>
                </table>
                <div style="background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 12px 16px; border-radius: 4px; font-size: 14px;">
                    <strong>Acción requerida:</strong> Se ha generado un registro en <em>Punto de Venta &gt; Configuración &gt; Incidencias de Tarifas</em>. Favor de ingresar a Odoo para revisar los horarios de tarifas asignados a esta sucursal y marcar la incidencia como resuelta.
                </div>
            </div>
            <div style="background-color: #f1f1f1; padding: 12px 24px; text-align: center; font-size: 12px; color: #999;">
                Sistema RDD - Alertas críticas de Punto de Venta
            </div>
        </div>
        """

        mail_values = {
            'subject': f"🚨 ALERTA TPV: Sin tarifa para {pos_name} ({comp_name})",
            'body_html': body_html,
            'email_to': recipients_str,
            'email_from': self.env.company.email or self.env.user.email or 'alertas@rdd.com',
        }

        try:
            self.env['mail.mail'].sudo().create(mail_values).send()
            _logger.info("Correo de ALERTA CRÍTICA de tarifa enviado a: %s", recipients_str)
        except Exception as mail_err:
            _logger.error("Error al enviar correo de alerta crítica en POS '%s': %s", pos_name, mail_err)

    def correo_lista_precio_pos(self, pos_configs, lista):
        """Backward compatible method."""
        return

    def _send_pricelist_change_email(self, pos, old_pl=None, new_pl=None, nombre_dia=None, now_local=None):
        new_pl = new_pl or self
        emails_list = []

        if new_pl.notification_emails:
            for em in new_pl.notification_emails.split(','):
                em = em.strip()
                if em and '@' in em:
                    emails_list.append(em)

        if new_pl.notify_pos_managers:
            employees = (
                getattr(pos, 'cashier_employee_ids', self.env['hr.employee']) |
                getattr(pos, 'manager_employee_ids', self.env['hr.employee']) |
                getattr(pos, 'supervised_employee_ids', self.env['hr.employee']) |
                getattr(pos, 'restrictive_employee_ids', self.env['hr.employee'])
            )
            for emp_email in employees.mapped('work_email'):
                if emp_email and emp_email.strip() and '@' in emp_email:
                    emails_list.append(emp_email.strip())

            company = getattr(pos, 'company_id', None)
            if company and getattr(company, 'email', False):
                emails_list.append(company.email.strip())

        emails_set = sorted(list({e for e in emails_list if e and '@' in e}))
        if not emails_set:
            _logger.info("Sin correos configurados para notificar cambio en POS '%s'", getattr(pos, 'name', 'TPV'))
            return

        recipients_str = ', '.join(emails_set)
        pos_name = getattr(pos, 'name', 'TPV')
        company_name = getattr(getattr(pos, 'company_id', None), 'name', 'RDD')
        old_name = getattr(old_pl, 'name', 'Ninguna') if old_pl else 'Ninguna'
        new_name = getattr(new_pl, 'name', 'Nueva Tarifa')

        if now_local:
            hora_str = now_local.strftime('%I:%M %p')
            fecha_str = now_local.strftime('%d/%m/%Y')
        else:
            now_dt = datetime.now()
            hora_str = now_dt.strftime('%H:%M')
            fecha_str = now_dt.strftime('%d/%m/%Y')

        dia_label = (nombre_dia or '').capitalize()
        fecha_display = f"{dia_label}, {fecha_str} ({hora_str})" if dia_label else f"{fecha_str} ({hora_str})"

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #714B67; color: #ffffff; padding: 18px 24px; text-align: center;">
                <h2 style="margin: 0; font-size: 20px;">Actualización de Lista de Precios en Punto de Venta</h2>
            </div>
            <div style="padding: 24px; background-color: #fafafa;">
                <p style="font-size: 15px; color: #333333; margin-top: 0;">
                    Se ha actualizado automáticamente la lista de precios predeterminada para la siguiente caja:
                </p>
                <table style="width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px;">
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555; width: 35%;">Sucursal / Empresa:</td>
                        <td style="padding: 12px 16px; color: #222;">{company_name}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555;">Caja / TPV:</td>
                        <td style="padding: 12px 16px; color: #222;">{pos_name}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555;">Fecha y Horario:</td>
                        <td style="padding: 12px 16px; color: #222;">{fecha_display}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #555;">Lista Anterior:</td>
                        <td style="padding: 12px 16px; color: #888;">{old_name}</td>
                    </tr>
                    <tr style="background-color: #eef7ee;">
                        <td style="padding: 12px 16px; font-weight: bold; color: #2e7d32;">Nueva Lista Activa:</td>
                        <td style="padding: 12px 16px; font-weight: bold; color: #2e7d32; font-size: 16px;">{new_name}</td>
                    </tr>
                </table>
                <p style="font-size: 13px; color: #777; margin-bottom: 0;">
                    Este cambio se aplicará a todas las nuevas ventas iniciadas en este Punto de Venta.
                </p>
            </div>
            <div style="background-color: #f1f1f1; padding: 12px 24px; text-align: center; font-size: 12px; color: #999;">
                Sistema RDD - Notificación automática de cambio de turnos y listas de precios
            </div>
        </div>
        """

        mail_values = {
            'subject': f"Cambio de Tarifa POS: {pos_name} ({company_name}) -> {new_name}",
            'body_html': body_html,
            'email_to': recipients_str,
            'email_from': self.env.company.email or self.env.user.email or 'notificaciones@rdd.com',
        }

        try:
            self.env['mail.mail'].sudo().create(mail_values).send()
            _logger.info("Correo de cambio de tarifa enviado a: %s", recipients_str)
        except Exception as mail_err:
            _logger.error("Error al enviar correo de cambio de tarifa en POS '%s': %s", pos_name, mail_err)

    @api.model
    def cron_pos_abierto(self):
        _logger.info("Iniciar cron pos abierto")
        open_sessions = self.env['pos.session'].search([('state', '=', 'opened')])
        pos_configs = open_sessions.config_id
        if not pos_configs:
            return

        nombre_pos_list = []
        emails_list = []

        for pos in pos_configs:
            company = getattr(pos, 'company_id', None)
            comp_name = getattr(company, 'name', '')
            nombre_pos_list.append(f"{pos.name} ({comp_name})" if comp_name else pos.name)
            employees = (
                getattr(pos, 'cashier_employee_ids', self.env['hr.employee']) |
                getattr(pos, 'manager_employee_ids', self.env['hr.employee']) |
                getattr(pos, 'supervised_employee_ids', self.env['hr.employee']) |
                getattr(pos, 'restrictive_employee_ids', self.env['hr.employee'])
            )
            for em in employees.mapped('work_email'):
                if em and '@' in em:
                    emails_list.append(em.strip())
            if company and getattr(company, 'email', False):
                emails_list.append(company.email.strip())

        nombre_pos = ', '.join(nombre_pos_list)
        emails = ', '.join(sorted(list({e for e in emails_list if e and '@' in e})))
        if not emails:
            _logger.info("No hay correos validos para notificar cajas abiertas.")
            return

        _logger.info("Cajas abiertas encontradas '%s'. Enviando aviso a: %s", nombre_pos, emails)

        mail_values = {
            'subject': 'Aviso: Cajas abiertas detectadas en el sistema',
            'body_html': f"<p>Se encontraron las siguientes cajas con sesión abierta: <strong>{nombre_pos}</strong>.</p>",
            'email_to': emails,
            'email_from': self.env.company.email or self.env.user.email,
        }

        try:
            self.env['mail.mail'].sudo().create(mail_values).send()
        except Exception as e:
            _logger.error("Error al enviar correo de cajas abiertas: %s", e)

    def _compute_price_rule(
            self, products, quantity, currency=None, uom=None, date=False, compute_price=True,
            **kwargs
    ):
        """ Low-level method - Mono pricelist, multi products
        Returns: dict{product_id: (price, suitable_rule) for the given pricelist}

        Note: self and self.ensure_one()

        :param products: recordset of products (product.product/product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param currency: record of currency (res.currency)
                         note: currency.ensure_one()
        :param uom: unit of measure (uom.uom record)
            If not specified, prices returned are expressed in product uoms
        :param date: date to use for price computation and currency conversions
        :type date: date or datetime
        :param bool compute_price: whether the price should be computed (default: True)

        :returns: product_id: (price, pricelist_rule)
        :rtype: dict
        """
        self and self.ensure_one()  # self is at most one record

        currency = currency or self.currency_id or self.env.company.currency_id
        currency.ensure_one()

        if not products:
            return {}

        if not date:
            # Used to fetch pricelist rules and currency rates
            date = fields.Datetime.now()

        # Fetch all rules potentially matching specified products/templates/categories and date
        rules = self._get_applicable_rules(products, quantity, date, uom=uom, **kwargs)

        results = {}
        for product in products:
            suitable_rule = self.env['product.pricelist.item']

            product_uom = product.uom_id
            target_uom = uom or product_uom  # If no uom is specified, fall back on the product uom

            # Compute quantity in product uom because pricelist rules are specified
            # w.r.t product default UoM (min_quantity, price_surchage, ...)
            if target_uom != product_uom:
                _logger.info(f"aqui xd  {product_uom} - {target_uom}")
                qty_in_product_uom = target_uom._compute_quantity(
                    quantity, product_uom, raise_if_failure=False
                )
            else:
                _logger.info(f"aqui xd2 {product_uom} - {target_uom}")
                qty_in_product_uom = quantity
            _logger.info(f"aqui xd3 {qty_in_product_uom}")
            _logger.info(f"aqui xd4 {quantity}")
            _logger.info(f"aqui xd4 {uom}")

            for rule in rules:
                if rule._is_applicable_for(product, qty_in_product_uom, uom=product_uom):
                    suitable_rule = rule
                    break

            if compute_price:
                price = suitable_rule._compute_price(
                    product, quantity, target_uom, date=date, currency=currency)
            else:
                # Skip price computation when only the rule is requested.
                price = 0.0
            results[product.id] = (price, suitable_rule.id)

        return results

class InheritProductPricelistitem(models.Model):
    _inherit = 'product.pricelist.item'

    markup_rdd = fields.Float('Markup RDD')

    @api.depends('price_discount', 'markup_rdd')
    def _compute_price_markup(self):
        for item in self:
            # item.price_markup = -item.price_discount
            if item.markup_rdd >= 100:
                item.price_markup = 0.0
            else:
                item.price_markup = (100/(1-(item.markup_rdd/100)))-100

    def _inverse_price_markup(self):
        for item in self:
            item.price_discount = -item.price_markup

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'markup_rdd' in vals:
                markup_rdd = vals['markup_rdd'] or 0.0
                if markup_rdd < 100:
                    markup = (100 / (1 - (markup_rdd / 100))) - 100
                    vals['price_discount'] = -markup
                    vals['price_markup'] = markup
                else:
                    vals['price_discount'] = 0.0
                    vals['price_markup'] = 0.0
        return super(InheritProductPricelistitem, self).create(vals_list)

    def write(self, vals):
        if 'markup_rdd' in vals:
            markup_rdd = vals['markup_rdd'] or 0.0
            if markup_rdd < 100:
                markup = (100 / (1 - (markup_rdd / 100))) - 100
                vals['price_discount'] = -markup
                vals['price_markup'] = markup
            else:
                vals['price_discount'] = 0.0
                vals['price_markup'] = 0.0
        return super(InheritProductPricelistitem, self).write(vals)


    def _compute_base_price(self, product, quantity, uom, date, currency):
        """ Compute the base price for a given rule

        :param product: recordset of product (product.product/product.template)
        :param float qty: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency conversions
        :param currency: currency in which the returned price must be expressed

        :returns: base price, expressed in provided pricelist currency
        :rtype: float
        """
        currency.ensure_one()

        rule_base = self.base or 'list_price'
        if rule_base == 'pricelist' and self.base_pricelist_id:
            price = self.base_pricelist_id._get_product_price(
                product, quantity, currency=self.base_pricelist_id.currency_id, uom=uom, date=date
            )
            src_currency = self.base_pricelist_id.currency_id
        elif rule_base == "standard_price":
            src_currency = product.cost_currency_id
            price = product._price_compute(rule_base, uom=uom, date=date)[product.id]
        else: # list_price
            src_currency = product.currency_id
            price = product._price_compute(rule_base, uom=uom, date=date)[product.id]

        if src_currency != currency:
            price = src_currency._convert(price, currency, self.env.company, date, round=False)

        return price

class DiasConfig(models.Model):
    _name = 'pricelist.dias'
    _description = 'Días de aplicación de listas de precios'
    _rec_name = 'nombre'

    nombre = fields.Char('Nombre')

    day = fields.Selection(
        selection=[
            ('lunes', 'Lunes'),
            ('martes', 'Martes'),
            ('miercoles', 'Miércoles'),
            ('jueves', 'Jueves'),
            ('viernes', 'Viernes'),
            ('sabado', 'Sábado'),
            ('domingo', 'Domingo'),
        ],
        string='Día de la Semana',
        
    )
