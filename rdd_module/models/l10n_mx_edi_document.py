# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import frozendict
from collections import defaultdict
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

TAX_TYPE_TO_CFDI_CODE = {'isr': '001', 'iva': '002', 'ieps': '003'}
CFDI_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'



class InheritL10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    @api.model
    def _get_global_invoice_cfdi_sequence(self, company, base_lines):
        """ Get or create the ir.sequence to be used to get the global invoice document name.

        :param company: The company owning the sequence.
        :return:        An ir.sequence record.
        """

        def grouping_function_base_line_tax_details(base_line, tax_data):
            tax = tax_data['tax']
            return {
                'tipo_factor': tax.l10n_mx_factor_type,
                'impuesto': TAX_TYPE_TO_CFDI_CODE.get(tax.l10n_mx_tax_type),
                'tax_amount_field': tax.amount,
                'is_withholding': tax.amount < 0.0,
                'skip': tax.l10n_mx_tax_type == 'local',
            }

        # Invoice lines.
        AccountTax = self.env['account.tax']
        base_lines_aggregated_values = AccountTax._aggregate_base_lines_tax_details(base_lines, grouping_function_base_line_tax_details)

        prefixes = set()
        suffixes = set()
        prefix = "GINV/"
        suffix = ""
        for line, aggregated_values in base_lines_aggregated_values:
            record = line['record']
            pos_line = self.env['pos.order.line'].browse(record.id)
            if pos_line and pos_line.order_id.session_id.config_id:
                prefix = pos_line.order_id.session_id.config_id.prefix
                suffix = pos_line.order_id.session_id.config_id.suffix
                if prefix:
                    prefixes.add(str(prefix))
                if suffix:
                    suffixes.add(str(suffix))

        if len(prefixes) > 1 or len(suffixes) > 1:
            raise UserError(
                "Las líneas del punto de venta tienen diferentes prefijos o sufijos.\n"
                f"Prefijos encontrados: {', '.join(prefixes)}\n"
                f"Sufijos encontrados: {', '.join(suffixes)}"
            )
        

        code = f'l10n_mx_global_invoice_cfdi_{prefix + suffix}'
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f"Global Invoice CFDI ({company.name})",
                'code': code,
                'company_id': company.id,
                'prefix': prefix + suffix, # SEQUENCIA EN FACTURA GLOBAL
                'implementation': 'standard',
                'use_date_range': True,
                'padding': 5,
            })
        return sequence

    @api.model
    def _add_global_invoice_cfdi_values(self, cfdi_values, cfdi_lines, document_date=None, periodicity='04',
                                        origin=None):
        """Add the generic values about the global invoice in 'cfdi_values'."""

        # -----------------------------
        # Helpers
        # -----------------------------
        def add_or_none(results, tax_values, key):
            """Keep None until first non-None appears, then accumulate."""
            value = tax_values.get(key)
            if value is not None:
                results[key] = results.get(key) or 0.0
                results[key] += value

        def normalize_periodicity(value):
            """
            SAT c_Periodicidad: 01 Diario, 02 Semanal, 03 Quincenal, 04 Mensual, 05 Bimestral
            Acepta: int, float (4.0), '4', '04', ('04','Mensual'), 'Mensual', etc.
            """
            if isinstance(value, (list, tuple)) and value:
                value = value[0]

            if value is None or value is False:
                value = '04'

            # float tipo 4.0
            if isinstance(value, float):
                if value.is_integer():
                    value = int(value)

            # int directo
            if isinstance(value, int):
                s = str(value).zfill(2)[-2:]
            else:
                s = str(value).strip()

                # si viene algo como "04 - Mensual", "04 Mensual", etc.
                # intentamos extraer el primer bloque numérico 1..2
                digits = ''.join(ch for ch in s if ch.isdigit())
                if digits:
                    # si venía "4" => "04", si venía "04" => "04"
                    s = digits.zfill(2)[-2:]
                else:
                    low = s.lower()
                    label_map = {
                        'diario': '01',
                        'semanal': '02',
                        'quincenal': '03',
                        'mensual': '04',
                        'bimestral': '05',
                    }
                    s = label_map.get(low, '04')

            allowed = {'01', '02', '03', '04', '05'}
            if s not in allowed:
                # si esto tronara, preferimos explotar aquí y no con error del PAC
                raise UserError(_("Periodicidad inválida para CFDI global: %s") % s)

            return s

        def get_concept_doc_name(concepto):
            """
            Odoo puede entregar conceptos con:
              - concepto['line'] (clásico)
              - concepto['base_line'] (algunas rutas)
              - o sin referencia a línea (conceptos técnicos)
            """
            line = concepto.get('line') or concepto.get('base_line') or {}
            doc_name = None

            if isinstance(line, dict):
                doc_name = line.get('document_name') or line.get('document') or line.get('name')
                rec = line.get('record')
                if not doc_name and rec and hasattr(rec, 'order_id'):
                    doc_name = rec.order_id.name

            return doc_name or concepto.get('document_name') or '/'

        # -----------------------------
        # Guards
        # -----------------------------
        if not cfdi_lines:
            raise UserError(_("No hay líneas CFDI para generar factura global."))

        currency = cfdi_lines[0].get('currency_id')
        if not currency:
            raise UserError(_("No se pudo determinar la moneda para la factura global."))

        # -----------------------------
        # Base values
        # -----------------------------
        self._add_base_cfdi_values(cfdi_values)
        self._add_currency_cfdi_values(cfdi_values, currency)
        self._add_document_origin_cfdi_values(cfdi_values, origin)
        self._add_customer_cfdi_values(cfdi_values, to_public=True)
        self._add_tax_objected_cfdi_values(cfdi_values, cfdi_lines)
        self._add_base_lines_cfdi_values(cfdi_values, cfdi_lines)

        # -----------------------------
        # Fecha CFDI: respetar forced datetime si existe
        # -----------------------------
        ctx = self.env.context
        fecha_str = None

        if ctx.get('_skip_recompute_fecha') and cfdi_values.get('fecha'):
            fecha_str = str(cfdi_values['fecha']).strip()
        elif ctx.get('_mx_cfdi_forced_datetime'):
            fecha_str = str(ctx['_mx_cfdi_forced_datetime']).strip()

        if fecha_str:
            # Asegurar formato YYYY-MM-DDTHH:MM:SS
            if 'T' not in fecha_str and ' ' in fecha_str:
                fecha_str = fecha_str.replace(' ', 'T', 1)
            if 'T' not in fecha_str:
                fecha_str = f"{fecha_str}T00:00:00"
            cfdi_date = fields.Date.to_date(fecha_str.split('T', 1)[0])
        else:
            cfdi_date = fields.Date.context_today(self)
            fecha_str = cfdi_date.strftime(CFDI_DATE_FORMAT)

        # -----------------------------
        # Sequence / folio / serie (usar fecha del CFDI para date_range)
        # -----------------------------
        sequence = self._get_global_invoice_cfdi_sequence(cfdi_values['root_company'], cfdi_lines)
        str_date = fields.Date.to_string(cfdi_date)

        folio = str(sequence.number_next)
        serie, _interpolated_suffix = sequence._get_prefix_suffix(date=str_date, date_range=str_date)

        # -----------------------------
        # Periodicity + InformacionGlobal
        # -----------------------------
        periodicity = normalize_periodicity(periodicity)

        document_date = document_date or cfdi_date
        month = document_date.month
        if periodicity == '05':
            # bimestral: 13..18
            periodicity_month = int(12 + ((month + (month % 2)) / 2))
        else:
            periodicity_month = month

        months_str = str(periodicity_month).rjust(2, '0')
        year_str = str(document_date.year)

        # ✅ ROBUSTO: keys minúsculas (core) + mayúsculas (templates alternos)
        info_global = {
            'periodicidad': periodicity,
            'meses': months_str,
            'ano': year_str,

            'Periodicidad': periodicity,
            'Meses': months_str,
            'Año': year_str,
            'Ano': year_str,  # por si un template usa ASCII
        }

        # -----------------------------
        # Tipo cambio (si no MXN) – promedio por documento
        # -----------------------------
        rates = []
        if currency.name != 'MXN':
            parents = set()
            for line in cfdi_lines:
                doc = line.get('document_name') or '/'
                rate = line.get('rate')
                if rate and doc not in parents:
                    parents.add(doc)
                    try:
                        rates.append(1 / rate)
                    except Exception:
                        pass

        cfdi_values.update({
            'sequence': sequence,
            'folio': folio,
            'serie': serie,

            'fecha': fecha_str,
            'tipo_cambio': (sum(rates) / len(rates)) if rates else None,

            # ✅ llave core
            'information_global': info_global,
            # ✅ alias por si tu template custom lo usa
            'informacion_global': info_global,

            'condiciones_de_pago': None,
            'tipo_de_comprobante': 'I',
        })

        # -----------------------------
        # Agrupar conceptos por (documento + huella de impuestos), removiendo descuentos
        # -----------------------------
        conceptos_map = defaultdict(lambda: {
            'clave_prod_serv': '01010101',
            'cantidad': 1,
            'clave_unidad': "ACT",
            'unidad': None,
            'cuenta_predial': None,
            'description': "Venta",
            'descuento': None,
            'importe': 0.0,
            'traslados_list': defaultdict(lambda: {'base': 0.0, 'importe': None}),
            'retenciones_list': defaultdict(lambda: {'base': 0.0, 'importe': None}),
        })

        for concepto in (cfdi_values.get('conceptos_list') or []):
            transferred_values_map = defaultdict(lambda: {'base': 0.0, 'importe': None})
            withholding_values_map = defaultdict(lambda: {'base': 0.0, 'importe': None})

            for result_dict, list_key in (
                    (withholding_values_map, 'retenciones_list'),
                    (transferred_values_map, 'traslados_list'),
            ):
                for tax_values in (concepto.get(list_key) or []):
                    tax_key = frozendict({
                        'impuesto': tax_values.get('impuesto'),
                        'tipo_factor': tax_values.get('tipo_factor'),
                        'tasa_o_cuota': tax_values.get('tasa_o_cuota'),
                    })
                    result_dict[tax_key]['base'] += (tax_values.get('base') or 0.0)
                    add_or_none(result_dict[tax_key], tax_values, 'importe')

            doc_name = get_concept_doc_name(concepto)

            key = frozendict({
                'document_name': doc_name,
                'traslados_list': frozenset(transferred_values_map.keys()),
                'retenciones_list': frozenset(withholding_values_map.keys()),
            })

            new_concepto = conceptos_map[key]
            new_concepto['no_identificacion'] = doc_name
            new_concepto['objeto_imp'] = concepto.get('objeto_imp')

            new_concepto['importe'] += (concepto.get('importe') or 0.0) - (concepto.get('descuento') or 0.0)

            for tax_result_dict, list_key in (
                    (withholding_values_map, 'retenciones_list'),
                    (transferred_values_map, 'traslados_list'),
            ):
                for tax_key, tax_amounts in tax_result_dict.items():
                    for amount_key in tax_amounts:
                        add_or_none(new_concepto[list_key][tax_key], tax_amounts, amount_key)

        # Append lines
        new_concepto_list = []
        for new_concepto in conceptos_map.values():
            new_concepto['valor_unitario'] = new_concepto.get('importe') or 0.0
            for list_key in ('traslados_list', 'retenciones_list'):
                for tax_key, tax_amounts in new_concepto[list_key].items():
                    tax_amounts.update(tax_key)
                new_concepto[list_key] = list(new_concepto[list_key].values())
            new_concepto_list.append(new_concepto)

        cfdi_values['conceptos_list'] = new_concepto_list

        # Remove the global discount safely
        subtotal = cfdi_values.get('subtotal') or 0.0
        descuento = cfdi_values.get('descuento') or 0.0
        cfdi_values['subtotal'] = subtotal - descuento
        cfdi_values['descuento'] = None
