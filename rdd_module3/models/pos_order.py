# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
from odoo.tools import float_round

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    global_invoice_id = fields.Many2one('account.move', string='Factura Global Cliente')
    l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name='l10n_mx_edi.payment.method',
        string="Payment Way",
        compute='_compute_l10n_mx_edi_payment_method_id',
        store=True,  # 👈 Esto permitirá usar el campo en group by SQL
    )

    def action_view_factura_global(self):
        self.ensure_one()
        if not self.global_invoice_id:
            raise UserError(_("Esta orden no tiene Factura Global Cliente ligada."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Factura Global Cliente"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.global_invoice_id.id,
            "target": "current",
        }

    def _l10n_mx_edi_cfdi_global_invoice_document_cancel(self, document, sat_state=None, *args, **kwargs):
        """
        Evita singleton cuando el recordset trae órdenes con diferentes attachments.
        Ejecuta la cancelación por grupo de attachment.

        Importante:
        En esta versión de Odoo Enterprise, el método super espera:
            _l10n_mx_edi_cfdi_global_invoice_document_cancel(document, sat_state)

        Por eso NO reenviamos 'error' ni argumentos extra al super.
        """
        res = None
        for attachment, orders in self.grouped("l10n_mx_edi_cfdi_attachment_id").items():
            if not orders:
                continue

            sup = super(PosOrder, orders)
            res = sup._l10n_mx_edi_cfdi_global_invoice_document_cancel(document, sat_state)

        return res

    @api.depends('payment_ids', 'payment_ids.payment_method_id')
    def _compute_l10n_mx_edi_payment_method_id(self):
        """
        Determina el método de pago SAT (FormaPago) predominante de la orden POS.
        - Si hay pagos, toma el método del pago con mayor monto.
        - Si no hay pagos, intenta usar 99.
        """
        for order in self:
            method = False
            if order.payment_ids:
                # pago con monto más alto
                best = max(order.payment_ids, key=lambda p: p.amount or 0.0)
                method = best.payment_method_id.l10n_mx_edi_payment_method_id
            if not method:
                method = order.company_id.l10n_mx_edi_payment_method_id
            order.l10n_mx_edi_payment_method_id = method

    def _build_invoice_lines_from_pos_consolidated(self, orders, company=None, include_refunds=False):
        """
        Genera account.move.line vals usando la misma lógica base del POS nativo
        para factura global CFDI:
        - venta base por orden original
        - localiza refunds ligados a esas líneas
        - netea devoluciones contra la misma huella fiscal
        - compacta al final por huella fiscal para crear la factura espejo / rectificativa

        include_refunds:
        - False: flujo normal (NO incluye órdenes refund).
        - True : sustitución (Rel 04): incluye devoluciones vinculadas para netear.
        """
        if not orders:
            raise UserError(_("No hay órdenes POS a consolidar."))

        env = self.env
        Document = env['l10n_mx_edi.document']

        # En ambos flujos exigimos misma compañía / moneda
        companies = orders.mapped('company_id')
        if len(companies) != 1:
            raise UserError(_("Todas las órdenes deben pertenecer a la misma compañía."))
        company = company or companies[0]

        currencies = orders.mapped('currency_id')
        if len(currencies) != 1:
            raise UserError(_("Todas las órdenes deben tener la misma moneda."))
        currency = currencies[0]

        def _to_id(v):
            if not v:
                return False
            return v if isinstance(v, int) else getattr(v, 'id', False)

        def _to_ids(v):
            if not v:
                return []
            if isinstance(v, (list, tuple, set)):
                return [x.id if hasattr(x, 'id') else int(x) for x in v]
            return getattr(v, 'ids', [])

        def _round(x):
            return float_round(x or 0.0, precision_rounding=currency.rounding)

        # -----------------------------------------------------------------
        # 1) Construir cfdi_lines con lógica nativa POS
        # -----------------------------------------------------------------
        cfdi_lines = []

        if not include_refunds:
            # Flujo normal: solo ventas base, sin refunds
            base_orders = orders.filtered(lambda o: not o.refunded_order_id)
            if not base_orders:
                raise UserError(_("No hay órdenes POS válidas (sin reembolsos) para consolidar."))

            for order in base_orders:
                order_lines = order.lines._l10n_mx_edi_cfdi_lines()
                base_lines = order_lines._prepare_tax_base_line_values()

                Document._add_base_lines_tax_amounts(base_lines, company)
                lines_dispatching = Document._dispatch_cfdi_base_lines(base_lines)

                if lines_dispatching.get('orphan_negative_lines'):
                    raise UserError(_(
                        "No fue posible distribuir algunas líneas negativas en la orden %s."
                    ) % (order.display_name,))

                result_lines = lines_dispatching['result_lines']
                for line in result_lines:
                    line['document_name'] = order.name

                cfdi_lines += result_lines

        else:
            # Flujo sustitución: misma estrategia que POS nativo
            base_orders = orders.filtered(lambda o: not o.refunded_order_id)

            if not base_orders:
                raise UserError(_("No hay órdenes base para construir la factura rectificativa."))

            for order in base_orders:
                # -----------------------------
                # A) Venta base
                # -----------------------------
                order_lines = order.lines._l10n_mx_edi_cfdi_lines()
                base_lines = order_lines._prepare_tax_base_line_values()

                Document._add_base_lines_tax_amounts(base_lines, company)
                lines_dispatching = Document._dispatch_cfdi_base_lines(base_lines)

                if lines_dispatching.get('orphan_negative_lines'):
                    raise UserError(_(
                        "No fue posible distribuir algunas líneas negativas en la venta base %s."
                    ) % (order.display_name,))

                base_lines = lines_dispatching['result_lines']
                base_line_ids = {x['id'] for x in base_lines}

                for base_line in base_lines:
                    base_line['document_name'] = order.name

                # -----------------------------
                # B) Refunds que apuntan a esas líneas
                # -----------------------------
                all_refund_order_lines = self.env['pos.order.line'].search([
                    ('refunded_orderline_id', 'in', order_lines.ids)
                ])._l10n_mx_edi_cfdi_lines()

                all_refund_base_lines = []

                for refund_order_lines in all_refund_order_lines.grouped('order_id').values():
                    refund_base_lines = refund_order_lines._prepare_tax_base_line_values()

                    # Igual que POS nativo: invertir qty para neteo
                    for refund_base_line in refund_base_lines:
                        refund_base_line['quantity'] *= -1

                    Document._add_base_lines_tax_amounts(refund_base_lines, company)

                    # 1) Primero despachar "positivos" dentro del refund
                    lines_dispatching = Document._dispatch_cfdi_base_lines(refund_base_lines)

                    if lines_dispatching['result_lines']:
                        raise UserError(_(
                            "No fue posible distribuir correctamente algunas líneas negativas "
                            "de la devolución ligada a %s."
                        ) % (order.display_name,))

                    # 2) Luego netear negativos restantes contra la venta base
                    refund_orphans = lines_dispatching['orphan_negative_lines']
                    lines_dispatching = Document._dispatch_cfdi_base_lines(base_lines + refund_orphans)

                    if lines_dispatching['orphan_negative_lines']:
                        raise UserError(_(
                            "Existen devoluciones que no pudieron netearse contra la venta original "
                            "en la orden %s. Esto suele pasar cuando la devolución no coincide en "
                            "producto/UoM/precio/impuestos o supera la cantidad vendida."
                        ) % (order.display_name,))

                    # Solo agregar líneas nuevas resultantes del neteo
                    all_refund_base_lines += [
                        x for x in lines_dispatching['result_lines']
                        if x['id'] not in base_line_ids
                    ]

                cfdi_lines += base_lines + all_refund_base_lines

        # -----------------------------------------------------------------
        # 2) Quitar líneas que quedaron en cero
        # -----------------------------------------------------------------
        cfdi_lines = [
            x for x in cfdi_lines
            if not x['currency_id'].is_zero(x['tax_details']['raw_total_excluded_currency'])
        ]

        if not cfdi_lines:
            raise UserError(_("No hay líneas para facturar (resultado vacío)."))

        # -----------------------------------------------------------------
        # 3) Redondeo fiscal igual al pipeline EDI
        # -----------------------------------------------------------------
        env['account.tax']._round_base_lines_tax_details(cfdi_lines, company)

        # -----------------------------------------------------------------
        # 4) Compactar por huella fiscal
        # -----------------------------------------------------------------
        buckets = {}
        original = len(cfdi_lines)

        for l in cfdi_lines:
            product_id = _to_id(l.get('product_id'))
            account_id = _to_id(l.get('account_id'))
            uom_id = _to_id(l.get('product_uom_id'))
            analytic_acc = _to_id(l.get('analytic_account_id'))
            analytic_tags = sorted(_to_ids(l.get('analytic_tag_ids')))

            price_unit = _round(l.get('price_unit', 0.0))
            discount = float_round(l.get('discount', 0.0) or 0.0, precision_digits=4)
            tax_ids = sorted(_to_ids(l.get('tax_ids')))

            key = (
                product_id,
                account_id,
                uom_id,
                price_unit,
                discount,
                tuple(tax_ids),
                analytic_acc,
                tuple(analytic_tags),
            )

            entry = buckets.get(key)
            if not entry:
                name = (
                        l.get('display_name')
                        or l.get('name')
                        or (product_id and env['product.product'].browse(product_id).display_name)
                        or '/'
                )
                buckets[key] = {
                    'name': name,
                    'qty': float(l.get('quantity', 0.0)),
                }
            else:
                entry['qty'] += float(l.get('quantity', 0.0))

        compacted = len(buckets)

        # -----------------------------------------------------------------
        # 5) Convertir a invoice_line_ids y validar que no queden qty negativas
        # -----------------------------------------------------------------
        tol = 1e-9
        invoice_line_vals = []

        for key, entry in buckets.items():
            (
                product_id, account_id, uom_id, price_unit, discount,
                tax_ids_tuple, analytic_acc, analytic_tags_tuple
            ) = key

            qty = float(entry.get('qty', 0.0))
            if abs(qty) <= tol:
                continue

            if qty < -tol:
                raise UserError(_(
                    "El consolidado resultó con cantidad NEGATIVA para un concepto.\n\n"
                    "Esto no es válido para una factura de ingreso. Revisa las devoluciones ligadas "
                    "o emite un CFDI de egreso por la diferencia."
                ))

            vals = {
                'product_id': product_id or False,
                'name': entry['name'],
                'quantity': qty,
                'price_unit': price_unit,
                'discount': discount,
                'tax_ids': [(6, 0, list(tax_ids_tuple))] if tax_ids_tuple else False,
            }
            if account_id:
                vals['account_id'] = account_id
            if uom_id:
                vals['product_uom_id'] = uom_id
            if analytic_acc:
                vals['analytic_account_id'] = analytic_acc
            if analytic_tags_tuple:
                vals['analytic_tag_ids'] = [(6, 0, list(analytic_tags_tuple))]

            invoice_line_vals.append((0, 0, vals))

        _logger.info(
            "[ConsolidatedBuilder] include_refunds=%s líneas EDI: %s -> compactadas: %s",
            include_refunds, original, compacted
        )

        if not invoice_line_vals:
            raise UserError(_("No se generaron líneas para la factura global (consolidado vacío)."))

        return invoice_line_vals

    @api.model
    def create_factura_global_cliente(self, uuid):
        # 1) Órdenes candidatas (aún sin factura global)
        orders = self.search([
            ('l10n_mx_edi_cfdi_uuid', '=', uuid),
            ('global_invoice_id', '=', False),
        ])
        if not orders:
            _logger.info("[GlobalInvoiceCliente] No hay órdenes pendientes para UUID %s", uuid)
            return

        # POLÍTICA: nunca reembolsos (flujo normal)
        orders = orders.filtered(lambda o: not o.refunded_order_id)
        if not orders:
            _logger.info("[GlobalInvoiceCliente] UUID %s: solo había reembolsos o no hay órdenes.", uuid)
            return

        # 2) Validaciones de consistencia
        companies = orders.mapped('company_id')
        if len(companies) != 1:
            raise UserError(_("Todas las órdenes deben pertenecer a la misma compañía."))
        company = companies[0]

        currencies = orders.mapped('currency_id')
        if len(currencies) > 1:
            raise UserError(_("Todas las órdenes deben tener la misma moneda."))
        currency = currencies[0] if currencies else company.currency_id

        # Diario fijo configurable
        journal = self.env['account.journal'].search([
            ('name', '=', 'Factura Global PDV'),
            ('company_id', '=', company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        if not journal:
            raise UserError(_('No se encontró el diario "Factura Global PDV" en la compañía %s.')
                            % company.display_name)

        # Partner genérico
        try:
            partner = self.env.ref('rdd_module3.res_partner_global_pdv')
        except Exception:
            raise UserError(_("Configura el partner genérico: rdd_module3.res_partner_global_pdv"))

        # 3) Método de pago predominante
        groups = [
            (sum(sub_orders.mapped('amount_total')), pm)
            for pm, sub_orders in orders.grouped('l10n_mx_edi_payment_method_id').items()
            if pm
        ]
        if groups:
            _max_total, payment_method = max(groups, key=lambda x: x[0])
        else:
            payment_method = self._get_payment_way_99()

        # 3) Líneas consolidadas (NUNCA reembolsos)
        invoice_line_ids = self._build_invoice_lines_from_pos_consolidated(
            orders, company=company, include_refunds=False
        )
        if not invoice_line_ids:
            raise UserError(_("No se generaron líneas para la factura global."))

        _logger.info("[GlobalInvoiceCliente] Se crearán %s líneas para UUID %s", len(invoice_line_ids), uuid)

        # 4) Crear factura
        dates = [d for d in orders.mapped('date_order') if d]
        inv_date = fields.Date.to_date(min(dates)) if dates else fields.Date.context_today(self)
        origin_str = ", ".join(orders.mapped('name'))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': journal.id,
            'currency_id': currency.id,
            'invoice_date': inv_date,
            'invoice_origin': origin_str,
            'l10n_mx_edi_cfdi_to_public': True,
            'l10n_mx_edi_usage': 'G03',
            'l10n_mx_edi_payment_method_id': payment_method.id if payment_method else False,
            'invoice_line_ids': invoice_line_ids,
        }

        invoice = self.env['account.move'].sudo().create(invoice_vals)

        # 5) Ligar factura a órdenes
        orders.write({'global_invoice_id': invoice.id})

        invoice.message_post(body=_(
            "Factura global cliente creada para UUID %s. Órdenes: %s"
        ) % (uuid, origin_str))

        return invoice

    # -------------------------------------------------------------------------
    #  Cancelación CFDI global (SAT) + sustitución (Relación 04)
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_cfdi_global_invoice_try_send(self, periodicity='04', origin=None, document_date=None):
        """ Create a CFDI global invoice.

        Ajustado para que en sustitución / rectificativa use la misma lógica nativa
        del POS:
        - parte de órdenes base (no refund)
        - busca refunds ligados por refunded_orderline_id
        - netea devoluciones contra la venta original
        - evita que los reembolsos se vuelvan a sumar

        :param periodicity:   The value to fill the 'Periodicidad' value.
        :param origin:        The origin of the GI when cancelling an existing one.
        :param document_date: Fecha base del periodo global (día 1 del mes).
        """
        ctx = dict(self.env.context)
        if document_date:
            ctx['_mx_global_document_date'] = fields.Date.to_string(document_date.replace(day=1))
        ctx['_mx_global_periodicity'] = (periodicity or ctx.get('_mx_global_periodicity') or '04')

        self = self.with_context(ctx)

        Document = self.env['l10n_mx_edi.document']
        orders = self._l10n_mx_edi_check_orders_for_global_invoice(origin=origin)

        # == Check the config ==
        # Validamos solo órdenes base y las devoluciones ligadas a ellas.
        base_orders = orders.filtered(lambda order: not order.refunded_order_id)
        refund_orders = self.env['pos.order']

        if base_orders:
            refund_orders = self.env['pos.order.line'].search([
                ('refunded_orderline_id.order_id', 'in', base_orders.ids)
            ])._l10n_mx_edi_cfdi_lines().order_id

        orders_to_check = base_orders | refund_orders

        errors = []
        for order in orders_to_check:
            errors += order._l10n_mx_edi_cfdi_check_order_config()
        if errors:
            orders._l10n_mx_edi_cfdi_global_invoice_document_sent_failed("\n".join(set(errors)))
            return

        # == Lock ==
        self.env['res.company']._with_locked_records(orders)

        # == Send ==
        def on_populate(cfdi_values):
            cfdi_lines = []

            for order in base_orders:
                # ---------------------------------------------------------
                # A) Venta base
                # ---------------------------------------------------------
                order_lines = order.lines._l10n_mx_edi_cfdi_lines()
                base_lines = order_lines._prepare_tax_base_line_values()

                Document._add_base_lines_tax_amounts(base_lines, cfdi_values['company'])
                lines_dispatching = Document._dispatch_cfdi_base_lines(base_lines)

                if lines_dispatching['orphan_negative_lines']:
                    cfdi_values['errors'] = [_(
                        "Failed to distribute some negative lines in order %s"
                    ) % order.name]
                    return

                base_lines = lines_dispatching['result_lines']
                base_line_ids = {x['id'] for x in base_lines}

                for base_line in base_lines:
                    base_line['document_name'] = order.name

                # ---------------------------------------------------------
                # B) Refunds ligados a esta venta
                # ---------------------------------------------------------
                all_refund_order_lines = self.env['pos.order.line'].search([
                    ('refunded_orderline_id', 'in', order_lines.ids)
                ])._l10n_mx_edi_cfdi_lines()

                all_refund_base_lines = []

                for refund_order_lines in all_refund_order_lines.grouped('order_id').values():
                    refund_base_lines = refund_order_lines._prepare_tax_base_line_values()

                    # Igual que el POS nativo: invertir qty para neteo
                    for refund_base_line in refund_base_lines:
                        refund_base_line['quantity'] *= -1

                    Document._add_base_lines_tax_amounts(refund_base_lines, cfdi_values['company'])

                    # 1) Despachar positivos dentro del refund
                    lines_dispatching = Document._dispatch_cfdi_base_lines(refund_base_lines)
                    if lines_dispatching['result_lines']:
                        cfdi_values['errors'] = [_(
                            "Failed to distribute some negative lines in refund linked to order %s"
                        ) % order.name]
                        return

                    # 2) Netear negativos restantes contra la venta base
                    refund_orphans = lines_dispatching['orphan_negative_lines']
                    lines_dispatching = Document._dispatch_cfdi_base_lines(base_lines + refund_orphans)
                    if lines_dispatching['orphan_negative_lines']:
                        cfdi_values['errors'] = [_(
                            "Some refund lines could not be matched against the original sale in order %s"
                        ) % order.name]
                        return

                    # Solo agregar líneas nuevas resultantes del neteo
                    all_refund_base_lines += [
                        x for x in lines_dispatching['result_lines']
                        if x['id'] not in base_line_ids
                    ]

                cfdi_lines += base_lines + all_refund_base_lines

            # Nada quedó: todo fue refund o quedó vacío
            cfdi_lines = [
                x for x in cfdi_lines
                if not x['currency_id'].is_zero(x['tax_details']['raw_total_excluded_currency'])
            ]
            if not cfdi_lines:
                cfdi_values['errors'] = ['empty_cfdi']
                return

            self.env['account.tax']._round_base_lines_tax_details(cfdi_lines, cfdi_values['company'])

            # Método de pago dominante
            payment_groups = []
            for payment_method, sub_orders in orders.grouped('l10n_mx_edi_payment_method_id').items():
                payment_groups.append((sum(sub_orders.mapped('amount_total')), payment_method))

            _biggest_amount_total, biggest_used_payment_method = max(
                payment_groups,
                key=lambda x: x[0],
            )

            Document._add_payment_policy_cfdi_values(
                cfdi_values,
                payment_method=biggest_used_payment_method
            )

            Document._add_global_invoice_cfdi_values(
                cfdi_values,
                cfdi_lines,
                periodicity=periodicity,
                origin=origin,
            )

            self.env['res.company']._with_locked_records(cfdi_values['sequence'])
            return cfdi_values['sequence']

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            if error == 'empty_cfdi':
                orders._l10n_mx_edi_cfdi_global_invoice_document_empty()
            else:
                orders._l10n_mx_edi_cfdi_global_invoice_document_sent_failed(
                    error,
                    cfdi_filename=cfdi_filename,
                    cfdi_str=cfdi_str,
                )

        def on_success(cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            self.env['l10n_mx_edi.document']._consume_global_invoice_cfdi_sequence(
                populate_return,
                int(cfdi_values['folio'])
            )
            orders._l10n_mx_edi_cfdi_global_invoice_document_sent(cfdi_filename, cfdi_str)

        qweb_template = self.env['l10n_mx_edi.document']._get_invoice_cfdi_template()
        cfdi_filename = "MX-Global-Invoice-4.0.xml".replace('/', '')
        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            qweb_template,
            cfdi_filename,
            on_populate,
            on_failure,
            on_success,
        )

    # ---------- NUEVO: helpers ----------

    def _get_payment_way_99(self):
        pm = self.env['l10n_mx_edi.payment.method'].search([('code', '=', '99')], limit=1)
        if not pm:
            raise UserError(_("No se encontró la forma de pago 99 (Por definir)."))
        return pm

    def _ensure_invoice_draft(self, invoice):
        invoice.ensure_one()
        if invoice.state == "posted":
            invoice.button_draft()
        elif invoice.state == "cancel":
            invoice.button_draft()
        return True

    def _create_global_replacement_invoice_draft(
            self, document, periodicity, forced_dt, payment_policy, payment_way_id
    ):
        origin_uuid = document.attachment_uuid
        if not origin_uuid:
            raise UserError(_("No se encontró UUID origen (attachment_uuid) del CFDI global."))

        origin_key = f"04|{origin_uuid}"

        # 1) Determinar órdenes fuente SIEMPRE por UUID origen (blindaje)
        def _match_origin_uuid(rs):
            return rs.filtered(lambda o: (
                    o.l10n_mx_edi_cfdi_uuid == origin_uuid
                    or (o.refunded_order_id and o.refunded_order_id.l10n_mx_edi_cfdi_uuid == origin_uuid)
            ))

        orders = _match_origin_uuid(self or self.env["pos.order"])

        if not orders:
            src = document._get_source_records() or self.env["pos.order"]
            orders = _match_origin_uuid(src)

        if not orders:
            orders = self.env["pos.order"].sudo().search([
                '|',
                ('l10n_mx_edi_cfdi_uuid', '=', origin_uuid),
                ('refunded_order_id.l10n_mx_edi_cfdi_uuid', '=', origin_uuid),
            ])
        if not orders:
            raise UserError(_("No hay órdenes POS asociadas al UUID %s.") % origin_uuid)

        # ✅ En sustitución (Rel 04) INCLUIMOS devoluciones del mismo UUID para netear el periodo.

        # 2) Guardas: una sola compañía y moneda (evita mezclas silenciosas)
        companies = orders.mapped("company_id")
        if len(companies) != 1:
            raise UserError(_(
                "Las órdenes fuente pertenecen a más de una compañía.\n"
                "UUID: %s\nCompañías: %s"
            ) % (origin_uuid, ", ".join(companies.mapped("name"))))
        company = companies[0]

        currencies = orders.mapped("currency_id")
        if len(currencies) != 1:
            raise UserError(_(
                "Las órdenes fuente pertenecen a más de una moneda.\n"
                "UUID: %s\nMonedas: %s"
            ) % (origin_uuid, ", ".join(currencies.mapped("name"))))
        currency = currencies[0]

        Move = self.env["account.move"].sudo()

        # 3) Política de existencia:
        # - Si existe DRAFT -> abrir
        # - Si existe POSTED -> bloquear
        draft = Move.search([
            ("move_type", "=", "out_invoice"),
            ("l10n_mx_edi_cfdi_origin", "=", origin_key),
            ("state", "=", "draft"),
        ], order="id desc", limit=1)
        if draft:
            return {
                "name": _("Factura de sustitución (GLOBAL)"),
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": draft.id,
                "view_mode": "form",
                "target": "current",
                "context": {"default_move_type": "out_invoice"},
            }

        posted = Move.search([
            ("move_type", "=", "out_invoice"),
            ("l10n_mx_edi_cfdi_origin", "=", origin_key),
            ("state", "=", "posted"),
        ], order="id desc", limit=1)
        if posted:
            msg_uuid = posted.l10n_mx_edi_cfdi_uuid or _("(sin UUID / sin timbrar)")
            raise UserError(_(
                "Ya existe una factura de sustitución para este CFDI en estado Aprobada (Posted).\n\n"
                "- Factura: %(name)s\n"
                "- CFDI Origen: %(origin)s\n"
                "- UUID sustituta: %(uuid)s\n\n"
                "Por seguridad, no se puede modificar desde el wizard.\n"
                "Si necesitas cambiarla, primero regrésala a Borrador y vuelve a intentar."
            ) % {
                                "name": posted.display_name,
                                "origin": origin_key,
                                "uuid": msg_uuid,
                            })

        # 4) Factura(s) ya ligadas a las órdenes (debe ser 1 o ninguna)
        invoices = orders.mapped("global_invoice_id").filtered(lambda inv: inv)
        if len(invoices) > 1:
            raise UserError(_(
                "Se detectó más de una factura ligada a las órdenes de este CFDI global.\n"
                "Revisa y corrige para que todas apunten a una sola factura antes de continuar."
            ))

        # 5) Partner genérico
        try:
            partner = self.env.ref("rdd_module3.res_partner_global_pdv")
        except Exception:
            raise UserError(_("Configura el partner genérico: rdd_module3.res_partner_global_pdv"))

        # 6) Forma de pago (solo exigir si policy=PUE)
        payment_way = self.env["l10n_mx_edi.payment.method"].browse(payment_way_id) if payment_way_id else False
        if payment_policy == "PUE" and not payment_way:
            raise UserError(_("Selecciona la 'Forma de pago' para PUE."))

        # Término de pago (si policy=PPD). Ojo: si payment_policy viene False (neutral), queda False.
        pay_term = self.env["account.payment.term"].search([], limit=1)

        def _term_for_policy(policy):
            return (pay_term.id or False) if policy == "PPD" else False

        # 7) Periodo global (mes/año) por min(date_order)
        dates = [d for d in orders.mapped("date_order") if d]
        period_date = (
            fields.Date.to_date(min(dates)).replace(day=1)
            if dates
            else fields.Date.context_today(self).replace(day=1)
        )

        # 8) Construir líneas consolidadas (ventas - devoluciones neteadas)
        line_vals = self._build_invoice_lines_from_pos_consolidated(
            orders, company=company, include_refunds=True
        )
        _logger.info("[ReplacementDraft] Preparadas %s líneas consolidadas", len(line_vals))
        if not line_vals:
            raise UserError(_("No se generaron líneas para la factura global (consolidado vacío)."))

        origin_str = ", ".join(orders.mapped("name"))

        # 9) Reuso de factura existente (sin origen 04)
        if invoices:
            invoice = invoices[0]

            # Regla: si ya tiene origen 04 -> abortar
            if invoice.l10n_mx_edi_cfdi_origin and invoice.l10n_mx_edi_cfdi_origin.startswith("04|"):
                raise UserError(_("La factura %s ya tiene Origen 04. Operación detenida.") % invoice.display_name)

            # Asegurar borrador para poder reescribir líneas/campos
            self._ensure_invoice_draft(invoice)

            # 🔥 FIX: desvincular órdenes viejas NO pertenecientes a este UUID/set
            old_orders = self.env["pos.order"].sudo().search([("global_invoice_id", "=", invoice.id)])
            to_unlink = old_orders - orders
            if to_unlink:
                to_unlink.write({"global_invoice_id": False})

            invoice_vals = {
                "l10n_mx_edi_cfdi_to_public": True,
                "partner_id": partner.id,
                "currency_id": currency.id,
                "invoice_origin": origin_str,
                "invoice_line_ids": [(5, 0, 0)] + line_vals,
                "invoice_payment_term_id": _term_for_policy(payment_policy),
                "l10n_mx_edi_payment_method_id": (payment_way.id if payment_policy == "PUE" else False),
                "l10n_mx_edi_cfdi_origin": origin_key,
                "l10n_mx_edi_usage": "G03",
                "x_is_global_pdv": True,
                "x_global_periodicity": periodicity,
                "invoice_date": period_date,
                "x_global_period_date": period_date,
            }
            if forced_dt:
                invoice_vals["x_cfdi_emission_datetime"] = forced_dt

            invoice.write(invoice_vals)

            # Asegurar que TODAS las órdenes del set apunten a esta factura
            orders.write({"global_invoice_id": invoice.id})

            invoice.message_post(
                body=_("Factura de sustitución GLOBAL reutilizada y actualizada (Relación 04 a %s).") % origin_uuid
            )
            for o in orders:
                o.message_post(body=_(
                    "Se reutilizó la factura de sustitución: "
                    "<a href=# data-oe-model='account.move' data-oe-id='%s'>%s</a>"
                ) % (invoice.id, invoice.display_name))

            return {
                "name": _("Factura de sustitución (GLOBAL)"),
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": invoice.id,
                "view_mode": "form",
                "target": "current",
                "context": {"default_move_type": "out_invoice"},
            }

        # 10) ✅ SI NO HAY FACTURA LIGADA: crear nueva factura borrador
        journal = self.env["account.journal"].sudo().search([
            ("name", "=", "Factura Global PDV"),
            ("company_id", "=", company.id),
            ("type", "=", "sale"),
        ], limit=1)
        if not journal:
            raise UserError(_('No se encontró el diario "Factura Global PDV" en la compañía %s.')
                            % company.display_name)

        create_vals = {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": journal.id,
            "currency_id": currency.id,
            "invoice_origin": origin_str,
            "invoice_line_ids": line_vals,
            "invoice_payment_term_id": _term_for_policy(payment_policy),
            "l10n_mx_edi_payment_method_id": (payment_way.id if payment_policy == "PUE" else False),
            "l10n_mx_edi_cfdi_to_public": True,
            "l10n_mx_edi_cfdi_origin": origin_key,
            "l10n_mx_edi_usage": "G03",
            "x_is_global_pdv": True,
            "x_global_periodicity": periodicity,
            "invoice_date": period_date,
            "x_global_period_date": period_date,
        }
        if forced_dt:
            create_vals["x_cfdi_emission_datetime"] = forced_dt

        invoice = Move.create(create_vals)

        # Ligar a órdenes
        orders.write({"global_invoice_id": invoice.id})

        invoice.message_post(
            body=_("Factura de sustitución GLOBAL creada (Relación 04 a %s).") % origin_uuid
        )
        for o in orders:
            o.message_post(body=_(
                "Se creó la factura de sustitución: "
                "<a href=# data-oe-model='account.move' data-oe-id='%s'>%s</a>"
            ) % (invoice.id, invoice.display_name))

        return {
            "name": _("Factura de sustitución (GLOBAL)"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
            "context": {"default_move_type": "out_invoice"},
        }