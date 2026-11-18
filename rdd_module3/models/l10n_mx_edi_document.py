# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import CFDI_DATE_FORMAT
except Exception:
    CFDI_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _rdd_find_move_from_cfdi_values(self, cfdi_values):
        """Encuentra el account.move de manera robusta (cfdi_values o context)."""
        move = (
            cfdi_values.get("invoice")
            or cfdi_values.get("move")
            or cfdi_values.get("record")
            or (self.move_id if self and hasattr(self, "move_id") else False)
        )
        if move:
            return move

        # Fallback por contexto (muy útil cuando cfdi_values no trae move)
        ctx = self.env.context
        active_model = ctx.get("active_model")
        active_id = ctx.get("active_id")
        if active_model == "account.move" and active_id:
            return self.env["account.move"].browse(active_id)

        # Otro fallback típico: res_model/res_id
        res_model = ctx.get("res_model")
        res_id = ctx.get("res_id")
        if res_model == "account.move" and res_id:
            return self.env["account.move"].browse(res_id)

        return False

    def _rdd_is_global_move(self, move):
        """Heurística: cuándo consideramos que esto debe comportarse como 'global'."""
        return bool(
            getattr(move, "x_is_global_pdv", False)
            or getattr(move, "l10n_mx_edi_cfdi_to_public", False)
            or getattr(move, "x_global_period_date", False)
            or getattr(move, "x_cfdi_emission_datetime", False)
        )

    def _rdd_apply_global_cfdi_overrides(self, cfdi_values):
        """
        Inyecta:
        - InformacionGlobal usando ctx['_mx_global_document_date'] o move.x_global_period_date/invoice_date
        - Fecha CFDI (Comprobante@Fecha) usando ctx['_mx_cfdi_forced_datetime'] o move.x_cfdi_emission_datetime
        - Receptor PUBLICO EN GENERAL

        Importante:
        - Debe funcionar también cuando todavía NO existe account.move
          (primer timbrado global desde POS).
        """
        move = self._rdd_find_move_from_cfdi_values(cfdi_values)
        ctx = self.env.context

        ctx_doc_date = ctx.get("_mx_global_document_date")
        ctx_forced_dt = ctx.get("_mx_cfdi_forced_datetime")
        ctx_periodicity = (ctx.get("_mx_global_periodicity") or "").strip()

        existing_ig = (
                cfdi_values.get("information_global")
                or cfdi_values.get("informacion_global")
                or {}
        )

        existing_periodicity = (
                existing_ig.get("periodicidad")
                or existing_ig.get("periodicity")
                or existing_ig.get("Periodicidad")
                or ""
        )

        is_global_ctx = bool(ctx_doc_date or ctx_forced_dt or ctx_periodicity)
        is_global_move = bool(move and self._rdd_is_global_move(move))
        is_global_existing = bool(existing_ig)

        if not (is_global_ctx or is_global_move or is_global_existing):
            return

        # Banderas usadas por templates
        cfdi_values["cfdi_to_public"] = True
        cfdi_values["to_public"] = True

        # 1) Periodo para InformacionGlobal (Meses/Año)
        if ctx_doc_date:
            period_dt = fields.Date.to_date(ctx_doc_date)
        elif move:
            period_dt = (
                    getattr(move, "x_global_period_date", False)
                    or move.invoice_date
                    or fields.Date.context_today(self)
            )
        else:
            existing_month = (
                    existing_ig.get("meses")
                    or existing_ig.get("months")
                    or existing_ig.get("Meses")
            )
            existing_year = (
                    existing_ig.get("ano")
                    or existing_ig.get("anio")
                    or existing_ig.get("year")
                    or existing_ig.get("Año")
                    or existing_ig.get("Ano")
            )
            if existing_month and existing_year:
                period_dt = fields.Date.to_date(
                    f"{int(existing_year):04d}-{int(existing_month):02d}-01"
                )
            else:
                period_dt = fields.Date.context_today(self)

        if period_dt:
            period_dt = period_dt.replace(day=1)

        periodicity = (
                ctx_periodicity
                or (getattr(move, "x_global_periodicity", None) if move else None)
                or existing_periodicity
                or "04"
        ).strip()
        periodicity = "".join(ch for ch in periodicity if ch.isdigit()) or "04"
        periodicity = periodicity.zfill(2)[-2:]

        months_str = f"{period_dt.month:02d}"
        year_str = str(period_dt.year)

        ig = {
            "periodicidad": periodicity,
            "meses": months_str,
            "ano": year_str,
            "anio": year_str,
            "periodicity": periodicity,
            "months": months_str,
            "year": year_str,
            "Periodicidad": periodicity,
            "Meses": months_str,
            "Año": year_str,
            "Ano": year_str,
        }
        cfdi_values["information_global"] = ig
        cfdi_values["informacion_global"] = ig

        # 2) Receptor: PUBLICO EN GENERAL
        receiver = cfdi_values.get("customer") or cfdi_values.get("receptor") or cfdi_values.get("receiver")
        if isinstance(receiver, dict):
            receiver["rfc"] = "XAXX010101000"
            receiver["vat"] = "XAXX010101000"
            receiver["name"] = "PUBLICO EN GENERAL"
            receiver["nombre"] = "PUBLICO EN GENERAL"

        # 3) Comprobante@Fecha
        if ctx_forced_dt:
            cfdi_values["fecha"] = ctx_forced_dt
            cfdi_values["date"] = ctx_forced_dt
            cfdi_values["_skip_recompute_fecha"] = True
        elif move:
            emission_dt = getattr(move, "x_cfdi_emission_datetime", False)
            if emission_dt:
                tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
                dt_local = fields.Datetime.context_timestamp(move.with_context(tz=tz_name), emission_dt)
                cfdi_values["fecha"] = dt_local.strftime(CFDI_DATE_FORMAT)
                cfdi_values["date"] = cfdi_values["fecha"]
                cfdi_values["_skip_recompute_fecha"] = True

        _logger.info(
            "[RDD] Overrides Global CFDI -> move=%s fecha=%s period=%s",
            getattr(move, "display_name", move.id) if move else "context-only",
            cfdi_values.get("fecha"),
            cfdi_values.get("information_global"),
        )

    # def _rdd_apply_global_cfdi_overrides(self, cfdi_values):
    #     """
    #     Inyecta:
    #     - InformacionGlobal usando ctx['_mx_global_document_date'] o move.x_global_period_date/invoice_date
    #     - Fecha CFDI (Comprobante@Fecha) usando ctx['_mx_cfdi_forced_datetime'] o move.x_cfdi_emission_datetime
    #     - Receptor PUBLICO EN GENERAL
    #     """
    #     move = self._rdd_find_move_from_cfdi_values(cfdi_values)
    #     if not move:
    #         return
    #
    #     if not self._rdd_is_global_move(move):
    #         return
    #
    #     # Banderas usadas por templates
    #     cfdi_values["cfdi_to_public"] = True
    #     cfdi_values["to_public"] = True
    #
    #     # 1) Periodo para InformacionGlobal (Meses/Año) con prioridad al contexto
    #     ctx_doc_date = self.env.context.get("_mx_global_document_date")
    #     if ctx_doc_date:
    #         period_dt = fields.Date.to_date(ctx_doc_date)
    #     else:
    #         period_dt = getattr(move, "x_global_period_date", False) or move.invoice_date or fields.Date.context_today(self)
    #     if period_dt:
    #         period_dt = period_dt.replace(day=1)
    #
    #     periodicity = (getattr(move, "x_global_periodicity", None) or "04").strip()
    #     periodicity = "".join(ch for ch in periodicity if ch.isdigit()) or "04"
    #     periodicity = periodicity.zfill(2)[-2:]
    #
    #     months_str = f"{period_dt.month:02d}"
    #     year_str = str(period_dt.year)
    #
    #     ig = {
    #         # core
    #         "periodicidad": periodicity,
    #         "meses": months_str,
    #         "ano": year_str,
    #         "anio": year_str,
    #         # compat EN
    #         "periodicity": periodicity,
    #         "months": months_str,
    #         "year": year_str,
    #         # compat SAT literal
    #         "Periodicidad": periodicity,
    #         "Meses": months_str,
    #         "Año": year_str,
    #         "Ano": year_str,
    #     }
    #     cfdi_values["information_global"] = ig
    #     cfdi_values["informacion_global"] = ig
    #
    #     # 2) Receptor: PUBLICO EN GENERAL (sobrescribe aunque el partner diga "GLOBAL PDV")
    #     receiver = cfdi_values.get("customer") or cfdi_values.get("receptor") or cfdi_values.get("receiver")
    #     if isinstance(receiver, dict):
    #         receiver["rfc"] = "XAXX010101000"
    #         receiver["vat"] = "XAXX010101000"
    #         receiver["name"] = "PUBLICO EN GENERAL"
    #         receiver["nombre"] = "PUBLICO EN GENERAL"
    #
    #     # 3) Comprobante@Fecha: prioridad a ctx forzado; si no, x_cfdi_emission_datetime
    #     forced_ctx = self.env.context.get("_mx_cfdi_forced_datetime")
    #     if forced_ctx:
    #         cfdi_values["fecha"] = forced_ctx
    #         cfdi_values["date"] = forced_ctx
    #         cfdi_values["_skip_recompute_fecha"] = True
    #     else:
    #         emission_dt = getattr(move, "x_cfdi_emission_datetime", False)
    #         if emission_dt:
    #             tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
    #             dt_local = fields.Datetime.context_timestamp(move.with_context(tz=tz_name), emission_dt)
    #             cfdi_values["fecha"] = dt_local.strftime(CFDI_DATE_FORMAT)
    #             cfdi_values["date"] = cfdi_values["fecha"]
    #             cfdi_values["_skip_recompute_fecha"] = True
    #
    #     _logger.info(
    #         "[RDD] Overrides Global CFDI -> move=%s fecha=%s period=%s",
    #         getattr(move, "display_name", move.id),
    #         cfdi_values.get("fecha"),
    #         cfdi_values.get("information_global"),
    #     )

    # ------------------------------------------------------------
    # Hook principal: _send_api
    # ------------------------------------------------------------
    @api.model
    def _send_api(self, company, qweb_template, cfdi_filename, on_populate, on_failure, on_success):
        """
        Envuelve on_populate y aplica overrides al dict que realmente se renderiza.
        """

        def wrapped_on_populate(cfdi_values):
            populate_return = on_populate(cfdi_values)

            # Si on_populate devuelve dict, ese es el "target" real a renderizar
            target = populate_return if isinstance(populate_return, dict) else cfdi_values

            # Aplica overrides (incluye Fecha desde ctx o x_cfdi_emission_datetime)
            self._rdd_apply_global_cfdi_overrides(target)

            # Sincroniza por si el flujo usa el cfdi_values original
            if target is not cfdi_values and isinstance(target, dict):
                cfdi_values.update(target)

            return populate_return

        return super()._send_api(company, qweb_template, cfdi_filename, wrapped_on_populate, on_failure, on_success)