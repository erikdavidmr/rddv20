# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta, date
import base64
import re


class L10nMxEdiInvoiceCancel(models.TransientModel):
    _inherit = "l10n_mx_edi.invoice.cancel"

    # ==========================
    # Campos extra (wizard)
    # ==========================
    replacement_global_period_date = fields.Date(
        string="Periodo global (mes/año)",
        help="Mes/Año que se usará para <cfdi:InformacionGlobal>. Se fuerza al día 1 automáticamente.",
    )
    replacement_payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Términos de pago (reemplazo)",
    )
    replacement_payment_way_id = fields.Many2one(
        comodel_name="l10n_mx_edi.payment.method",
        string="Forma de pago (reemplazo)",
        help="Forma de pago SAT para el reemplazo. Si eliges PPD, se recomienda '99 - Por definir'.",
    )
    replacement_emission_datetime = fields.Datetime(
        string="Fecha/hora de emisión (reemplazo)",
        help="Fecha y hora que se usará como 'Fecha' del CFDI de reemplazo.",
        default=lambda self: fields.Datetime.now(),
    )
    has_substitution_doc = fields.Boolean(
        string="Tiene CFDI sustituto",
        compute="_compute_has_substitution_doc",
        store=False,
        compute_sudo=True,
    )

    # ==========================
    # Onchange
    # ==========================
    @api.onchange("replacement_global_period_date")
    def _onchange_replacement_global_period_date(self):
        for w in self:
            if w.replacement_global_period_date:
                w.replacement_global_period_date = w.replacement_global_period_date.replace(day=1)

    def _validate_forced_datetime(self, forced_dt):
        if not forced_dt:
            return
        now = fields.Datetime.now()
        if (now - forced_dt) > timedelta(hours=72) or forced_dt > now:
            raise UserError(_("Fecha de emisión inválida: supera 72h o es a futuro."))

    def _compute_period_date_for_global(self, document, orders, replacement):
        # 1) Si usuario eligió periodo en wizard, gana
        if self.replacement_global_period_date:
            return self.replacement_global_period_date.replace(day=1)

        # 2) Si ya hay en factura, usarla
        if getattr(replacement, "x_global_period_date", False):
            return replacement.x_global_period_date.replace(day=1)

        # 3) Default: min(date_order) de órdenes
        dates = [d for d in orders.mapped("date_order") if d]
        if dates:
            return fields.Date.to_date(min(dates)).replace(day=1)

        # 4) fallback
        return fields.Date.context_today(self).replace(day=1)

    def _apply_replacement_fields(self, replacement, document=None, orders=None):
        vals = {}

        # política de pago SAT (PUE/PPD)
        if self.replacement_payment_term_id:
            vals["invoice_payment_term_id"] = self.replacement_payment_term_id.id

        if self.replacement_payment_way_id:
            vals["l10n_mx_edi_payment_method_id"] = self.replacement_payment_way_id.id

        if self.replacement_emission_datetime:
            vals["x_cfdi_emission_datetime"] = self.replacement_emission_datetime

        if vals:
            replacement.write(vals)

    @api.depends("document_id", "mode", "need_replacement_invoice_button")
    def _compute_has_substitution_doc(self):
        for w in self:
            flag = False

            if w.mode == "ginvoice" and w.document_id and w.need_replacement_invoice_button:
                orders = w.document_id._get_source_records() or self.env["pos.order"]

                replacement_moves = orders.mapped("global_invoice_id").filtered(
                    lambda m: m.move_type == "out_invoice" and m.state == "posted"
                )

                flag = any(bool(m.l10n_mx_edi_cfdi_uuid) for m in replacement_moves)

            w.has_substitution_doc = flag

    def action_create_replacement_invoice(self):
        self.ensure_one()

        # Flujo normal (factura normal)
        if self.mode == "invoice":
            return super().action_create_replacement_invoice()

        # Si no es factura global, delegar
        if self.mode != "ginvoice":
            return super().action_create_replacement_invoice()

        document = self.document_id
        if not document:
            raise UserError(_("No hay documento CFDI global seleccionado."))

        uuid_orig = document.attachment_uuid
        if not uuid_orig:
            raise UserError(_("No se encontró UUID origen (attachment_uuid) del CFDI global."))

        # 1) Órdenes fuente: SIEMPRE filtradas por UUID origen (blindaje)
        orders = document._get_source_records() or self.env["pos.order"]
        orders = orders.filtered(lambda o: (
            o.l10n_mx_edi_cfdi_uuid == uuid_orig
            or (o.refunded_order_id and o.refunded_order_id.l10n_mx_edi_cfdi_uuid == uuid_orig)
        ))

        # Fallback: si _get_source_records trae algo raro o vacío, buscamos directo por UUID
        if not orders:
            orders = self.env["pos.order"].sudo().search([
                '|',
                ("l10n_mx_edi_cfdi_uuid", "=", uuid_orig),
                ("refunded_order_id.l10n_mx_edi_cfdi_uuid", "=", uuid_orig),
            ])

        if not orders:
            raise UserError(_("No hay órdenes POS fuente para este CFDI global (UUID %s).") % uuid_orig)

        # Guard: una sola compañía (evita mezclas silenciosas)
        companies = orders.mapped("company_id")
        if len(companies) != 1:
            raise UserError(_(
                "Las órdenes fuente pertenecen a más de una compañía.\n"
                "UUID: %s\nCompañías: %s"
            ) % (uuid_orig, ", ".join(companies.mapped("name"))))

        forced = self.replacement_emission_datetime
        # Opcional: puedes quitar esta validación y dejarla para el timbrado si solo estás creando borrador.
        self._validate_forced_datetime(forced)

        periodicity = self.periodicity or "04"
        origin_key = f"04|{uuid_orig}"

        Move = self.env["account.move"].sudo()

        # ==========================
        # Política:
        # 1) Si hay draft: reusar/actualizar
        # 2) Si hay posted: bloquear con alerta
        # 3) Si hay cancel (y no hay draft/posted): crear nuevo borrador
        # ==========================

        # 1) Draft (si existe, gana)
        replacement = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "draft"),
            ("l10n_mx_edi_cfdi_origin", "=", origin_key),
        ], order="id desc", limit=1)

        if replacement:
            # Actualizar campos del wizard
            self._apply_replacement_fields(replacement, document=document, orders=orders)

            # Periodo final para InformacionGlobal (Meses/Año)
            period_date = self._compute_period_date_for_global(document, orders, replacement)
            replacement.write({
                "x_global_period_date": period_date,
                "invoice_date": period_date,
            })

            return {
                "type": "ir.actions.act_window",
                "name": _("Factura de sustitución (GLOBAL)"),
                "res_model": "account.move",
                "res_id": replacement.id,
                "view_mode": "form",
                "target": "current",
            }

        # 2) Posted/Aprobada (si existe, NO crear/NO abrir: solo alertar)
        posted = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("l10n_mx_edi_cfdi_origin", "=", origin_key),
        ], order="id desc", limit=1)

        if posted:
            msg_uuid = posted.l10n_mx_edi_cfdi_uuid or _("(sin UUID disponible)")
            raise UserError(_(
                "Ya existe una factura de sustitución para este CFDI en estado **Aprobada (Posted)**.\n\n"
                "- Factura: %(name)s\n"
                "- CFDI Origen: %(origin)s\n"
                "- UUID sustituta: %(uuid)s\n\n"
                "Por seguridad, no se puede modificar desde el wizard.\n"
                "Si necesitas cambiarla, primero regrésala a **Borrador** y vuelve a intentar."
            ) % {
                "name": posted.name or f"ID {posted.id}",
                "origin": origin_key,
                "uuid": msg_uuid,
            })

        # 3) Cancelada (si existe y no hay draft/posted) -> crear NUEVO borrador

        # Crear borrador (haya cancelada o no exista nada)
        action = orders._create_global_replacement_invoice_draft(
            document=document,
            periodicity=periodicity,
            forced_dt=forced,
            payment_policy=False,  # neutral: wizard define
            payment_way_id=(self.replacement_payment_way_id.id if self.replacement_payment_way_id else False),
        )

        # Tomar el draft recién creado (o el más nuevo)
        replacement = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "draft"),
            ("l10n_mx_edi_cfdi_origin", "=", origin_key),
        ], order="id desc", limit=1)

        if not replacement:
            raise UserError(_("No se encontró la factura borrador de sustitución %s.") % origin_key)

        # Aplicar campos del wizard
        self._apply_replacement_fields(replacement, document=document, orders=orders)

        period_date = self._compute_period_date_for_global(document, orders, replacement)
        replacement.write({
            "x_global_period_date": period_date,
            "invoice_date": period_date,
        })

        return action or {
            "type": "ir.actions.act_window",
            "name": _("Factura de sustitución (GLOBAL)"),
            "res_model": "account.move",
            "res_id": replacement.id,
            "view_mode": "form",
            "target": "current",
        }