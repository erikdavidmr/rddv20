# -*- coding: utf-8 -*-
# models/l10n_mx_edi_global_invoice_create.py

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError
from datetime import timedelta


class L10nMxEdiGlobalInvoiceCreate(models.TransientModel):
    _inherit = 'l10n_mx_edi.global_invoice.create'

    pos_order_ids = fields.Many2many(comodel_name='pos.order')

    emission_datetime = fields.Datetime(
        string="Fecha/hora de emisión",
        help="Si se establece, se usará como 'Fecha' del CFDI (no futura y máx. 72h hacia atrás).",
        default=lambda self: fields.Datetime.now(),
    )

    global_period_date = fields.Date(
        string="Periodo global (mes/año)",
        help="Mes/Año para <cfdi:InformacionGlobal>. El sistema solo tomara el mes y año elegidos.",
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )

    @api.onchange('global_period_date')
    def _onchange_global_period_date(self):
        """Forzar día 1 para que el usuario solo elija mes/año."""
        for w in self:
            if w.global_period_date:
                w.global_period_date = w.global_period_date.replace(day=1)

    @api.model
    def default_get(self, fields_list):
        results = super().default_get(fields_list)

        # Si el wizard se abre desde POS Orders (active_ids)
        if self.env.context.get('active_model') == 'pos.order':
            active_ids = self.env.context.get('active_ids') or []
            if active_ids and 'pos_order_ids' in fields_list and not results.get('pos_order_ids'):
                orders = self.env['pos.order'].browse(active_ids)
                orders = orders._l10n_mx_edi_check_orders_for_global_invoice()

                # ✅ coherencia: emisión normal NO incluye reembolsos
                orders = orders.filtered(lambda o: not o.refunded_order_id)

                results['pos_order_ids'] = [Command.set(orders.ids)]

                # ✅ Default del periodo: mes/año basado en las órdenes (mínimo date_order)
                if 'global_period_date' in fields_list and not results.get('global_period_date'):
                    dates = [d for d in orders.mapped('date_order') if d]
                    if dates:
                        period_date = fields.Date.to_date(min(dates)).replace(day=1)
                    else:
                        period_date = fields.Date.context_today(self).replace(day=1)
                    results['global_period_date'] = period_date

        return results

    def action_create_global_invoice(self):
        self.ensure_one()

        # ✅ Validación emisión (72h y no futuro)
        if self.emission_datetime:
            now = fields.Datetime.now()  # UTC
            forced = self.emission_datetime  # UTC
            if forced > now or (now - forced) > timedelta(hours=72):
                raise UserError(_("La fecha de emisión excede 72 horas o es futura. Selecciona una fecha válida."))

        # ✅ Validación periodo (no futuro)
        if self.global_period_date:
            period_date = self.global_period_date.replace(day=1)
            today = fields.Date.context_today(self)
            if period_date > today.replace(day=1):
                raise UserError(_("El periodo global no puede estar en el futuro."))

        ctx = dict(self.env.context)

        # Fecha/hora CFDI (Comprobante@Fecha) en string local
        if self.emission_datetime:
            tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
            dt_local = fields.Datetime.context_timestamp(self.with_context(tz=tz_name), self.emission_datetime)
            ctx['_mx_cfdi_forced_datetime'] = dt_local.strftime('%Y-%m-%dT%H:%M:%S')
            ctx['_skip_recompute_fecha'] = True

        # Periodo InformacionGlobal (Meses/Año) (día 1)
        if self.global_period_date:
            ctx['_mx_global_document_date'] = fields.Date.to_string(self.global_period_date.replace(day=1))

        # Periodicidad global
        ctx['_mx_global_periodicity'] = self.periodicity

        # Si viene desde POS -> timbrar por flujo POS y cerrar wizard
        if self.pos_order_ids:
            # ✅ coherencia: emisión normal NO incluye reembolsos
            orders = self.pos_order_ids.filtered(lambda o: not o.refunded_order_id)
            if not orders:
                raise UserError(_("No hay órdenes válidas para factura global (todas son reembolsos)."))

            orders.with_context(ctx)._l10n_mx_edi_cfdi_global_invoice_try_send(
                periodicity=self.periodicity,
                document_date=(self.global_period_date.replace(day=1) if self.global_period_date else None),
            )
            return {'type': 'ir.actions.act_window_close'}

        # Fallback: comportamiento estándar
        return super(L10nMxEdiGlobalInvoiceCreate, self.with_context(ctx)).action_create_global_invoice()

    # def action_create_global_invoice(self):
    #     self.ensure_one()
    #
    #     # ✅ Validación emisión (72h y no futuro)
    #     if self.emission_datetime:
    #         now = fields.Datetime.now()  # UTC
    #         forced = self.emission_datetime  # UTC
    #         if forced > now or (now - forced) > timedelta(hours=72):
    #             raise UserError(_("La fecha de emisión excede 72 horas o es futura. Selecciona una fecha válida."))
    #
    #     # ✅ Validación periodo (no futuro)
    #     if self.global_period_date:
    #         period_date = self.global_period_date.replace(day=1)
    #         today = fields.Date.context_today(self)
    #         if period_date > today.replace(day=1):
    #             raise UserError(_("El periodo global no puede estar en el futuro."))
    #
    #     ctx = dict(self.env.context)
    #
    #     # Fecha/hora CFDI (Comprobante@Fecha) en string local
    #     if self.emission_datetime:
    #         tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
    #         dt_local = fields.Datetime.context_timestamp(self.with_context(tz=tz_name), self.emission_datetime)
    #         ctx['_mx_cfdi_forced_datetime'] = dt_local.strftime('%Y-%m-%dT%H:%M:%S')
    #         ctx['_skip_recompute_fecha'] = True
    #
    #     # Periodo InformacionGlobal (Meses/Año) (día 1)
    #     if self.global_period_date:
    #         ctx['_mx_global_document_date'] = fields.Date.to_string(self.global_period_date.replace(day=1))
    #
    #     # Si viene desde POS -> timbrar por flujo POS y cerrar wizard
    #     if self.pos_order_ids:
    #         # ✅ coherencia: emisión normal NO incluye reembolsos
    #         orders = self.pos_order_ids.filtered(lambda o: not o.refunded_order_id)
    #         if not orders:
    #             raise UserError(_("No hay órdenes válidas para factura global (todas son reembolsos)."))
    #
    #         try:
    #             orders.with_context(ctx)._l10n_mx_edi_cfdi_global_invoice_try_send(
    #                 periodicity=self.periodicity,
    #                 document_date=(self.global_period_date.replace(day=1) if self.global_period_date else None),
    #             )
    #         except TypeError:
    #             orders.with_context(ctx)._l10n_mx_edi_cfdi_global_invoice_try_send(
    #                 periodicity=self.periodicity
    #             )
    #         return {'type': 'ir.actions.act_window_close'}
    #
    #     # Fallback: comportamiento estándar
    #     return super(L10nMxEdiGlobalInvoiceCreate, self.with_context(ctx)).action_create_global_invoice()