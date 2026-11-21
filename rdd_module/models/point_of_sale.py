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
    

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _create_bank_payment_line(self, session, amount, account=None, message=None, partner=None, foreign_currency=None, amount_currency=None):
        if not self.outstanding_account_id:
            chart_template = self.with_context(allowed_company_ids=self.company_id.root_id.ids).env['account.chart.template']
            fallback_account = (
                chart_template.ref('account_journal_payment_debit_account_id', raise_if_not_found=False)
                or self.company_id.transfer_account_id
                or self.journal_id.default_account_id
            )
            if fallback_account:
                self.env.cr.execute(
                    "UPDATE pos_payment_method SET outstanding_account_id = %s WHERE id = %s",
                    (fallback_account.id, self.id),
                )
                self.invalidate_recordset(['outstanding_account_id'])
        return super()._create_bank_payment_line(session, amount, account, message, partner, foreign_currency, amount_currency)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _create_session_account_move(self, orders):
        for pm in orders.payment_ids.payment_method_id.filtered(lambda p: p.type == 'bank' and not p.outstanding_account_id):
            chart_template = self.with_context(allowed_company_ids=pm.company_id.root_id.ids).env['account.chart.template']
            fallback_account = (
                chart_template.ref('account_journal_payment_debit_account_id', raise_if_not_found=False)
                or pm.company_id.transfer_account_id
                or pm.journal_id.default_account_id
            )
            if fallback_account:
                self.env.cr.execute(
                    "UPDATE pos_payment_method SET outstanding_account_id = %s WHERE id = %s",
                    (fallback_account.id, pm.id),
                )
                pm.invalidate_recordset(['outstanding_account_id'])
        return super()._create_session_account_move(orders)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_is_cfdi_invoice(self):
        self.ensure_one()
        # Las facturas de cierre de sesión de PDV (POSC/...) son pólizas de cierre contable,
        # no deben timbrarse directamente como CFDI individual para evitar duplicidad fiscal.
        # El CFDI Global se emite desde las órdenes de venta del PDV.
        if self.pos_session_ids:
            return False
        return super()._l10n_mx_edi_is_cfdi_invoice()
