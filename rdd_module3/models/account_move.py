from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    pos_order_count = fields.Integer(string='Órdenes POS', compute='_compute_pos_order_count')
    config_id = fields.Many2one('pos.config', string='PDV Relacionado')
    # Auxiliares para marcado de "Factura Global PDV (sustitución)"
    x_is_global_pdv = fields.Boolean(string="Es Global PDV (Sustitución)", default=False)
    x_global_periodicity = fields.Selection(
        selection=[('01', 'Diaria'), ('02', 'Semanal'), ('03', 'Quincenal'), ('04', 'Mensual')],
        string="Periodicidad Global",
        default='04')
    # ✅ NUEVO: Periodo global (Meses/Año de InformacionGlobal) y emisión CFDI (Comprobante@Fecha)
    x_global_period_date = fields.Date(
        string="Periodo Global (fecha base)",
        help="Fecha base (normalmente el día 1 del mes) usada para cfdi:InformacionGlobal Meses/Año.",
        copy=False,
    )
    x_cfdi_emission_datetime = fields.Datetime(
        string="Fecha/hora emisión CFDI",
        help="Si se define, se usará como Comprobante@Fecha cuando se timbre sin contexto (timbrado nativo).",
        copy=False,
    )

    def create_pos_cash_payment(self):
        self.ensure_one()

        _logger.info("Iniciando creación de pago para factura global %s (%s)", self.name, self.id)

        # Buscar pagos POS relacionados con la misma factura global
        pos_payments = self.env['pos.payment'].search([
            ('pos_order_id.global_invoice_id', '=', self.id),
        ])
        _logger.info("Pagos POS relacionados encontrados: %s", pos_payments.ids)

        if not pos_payments:
            raise UserError(_('No se encontraron pagos POS relacionados con esta factura global.'))

        # Tomar el método de pago del primer pago POS relacionado
        payment_method = pos_payments[0].payment_method_id
        if not payment_method:
            raise UserError(_('No se encontró método de pago en el pago POS relacionado.'))

        _logger.info("Método de pago POS encontrado: %s (%s)", payment_method.name, payment_method.id)

        # Tomar el diario desde el método de pago POS
        journal = payment_method.journal_id
        if not journal:
            raise UserError(
                _('El método de pago POS "%s" no tiene configurado un diario.') % payment_method.display_name)

        _logger.info("Diario determinado a partir del método de pago POS: %s (%s)", journal.name, journal.id)

        memo_text = _('Cierre de caja "%s" "%s"') % (
            self.config_id.name or '',
            self.l10n_mx_edi_payment_method_id.name or '',
        )
        _logger.info("Memo para el pago: %s", memo_text)
        _logger.info("Monto del pago: %.2f", self.amount_total)

        payment_method_line = self.env['account.payment.method.line'].search([
            ('journal_id', '=', journal.id),
            ('payment_method_id.name', 'ilike', 'manual'),
        ], limit=1)
        if not payment_method_line:
            raise UserError(
                _('No se encontró un método de pago Manual configurado en el diario %s.') % journal.display_name)
        _logger.info("Método de pago contable seleccionado: %s", payment_method_line.display_name)

        pago = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.env.company.partner_id.id,
            'amount': self.amount_total,
            'payment_method_line_id': payment_method_line.id,
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'memo': memo_text,
        })

        pago.action_post()
        message = _(
            'Se generó a partir de la factura global: <a href=# data-oe-model="account.move" data-oe-id="%s">%s</a>') % (
                      self.id, self.name)
        pago.message_post(body=message)
        message = _(
            'Se creó el pago de cierre de caja: <a href=# data-oe-model="account.payment" data-oe-id="%s">%s</a>') % (
                      pago.id, pago.name)
        self.message_post(body=message)

        _logger.info("Pago creado y publicado correctamente: %s", pago.id)

    def _compute_pos_order_count(self):
        for move in self:
            move.pos_order_count = self.env['pos.order'].search_count([('global_invoice_id', '=', move.id)])

    def action_view_pos_orders(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Órdenes POS'),
            'res_model': 'pos.order',
            'view_mode': 'list',
            'domain': [('global_invoice_id', '=', self.id)],
            'context': {'create': False},
            'target': 'current',
        }
