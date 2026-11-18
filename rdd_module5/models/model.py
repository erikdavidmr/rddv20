# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = "pos.config"

    not_print_qr_url = fields.Boolean(string="No imprimir URL QR",)

    @api.model
    def _load_pos_data_fields(self, config):
        # Odoo 20's pos.config currently inherits the generic loader, whose
        # default field list is empty. Keep the standard POS config payload
        # here so core _load_pos_data_read and the POS client receive it.
        fields_to_load = [
            "id", "name", "display_name", "access_token", "active", "uuid",
            "company_id", "currency_id", "journal_id", "payment_method_ids",
            "fast_payment_method_ids", "use_fast_payment", "cash_control",
            "pricelist_id", "available_pricelist_ids", "use_pricelist",
            "fiscal_position_ids", "default_fiscal_position_id", "iface_tax_included",
            "iface_available_categ_ids", "iface_big_scrollbars", "iface_print_auto",
            "iface_printbill", "iface_group_by_categ", "show_product_images",
            "show_category_images", "restrict_price_control", "manual_discount",
            "is_margins_costs_accessible_to_every_user", "use_presets",
            "default_preset_id", "available_preset_ids", "module_pos_restaurant",
            "module_pos_hr", "module_pos_discount", "tip_product_id",
            "iface_tipproduct", "preparation_printer_ids", "receipt_printer_ids",
            "use_order_printer", "basic_receipt", "receipt_header", "receipt_footer",
            "other_devices", "rounding_method", "cash_rounding", "only_round_cash_method",
            "auto_validate_electronic_payment", "set_maximum_difference",
            "amount_authorized_diff", "company_has_template", "current_user_id",
            "current_session_id", "current_session_state", "session_ids",
            "has_active_session", "last_session_closing_date", "pos_session_username",
            "pos_session_state", "pos_session_duration", "trusted_config_ids",
            "note_ids", "default_bill_ids", "limit_categories", "tax_regime_selection",
            "fallback_nomenclature_id", "use_header_or_footer", "use_closing_entry_by_product",
            "module_pos_avatax", "module_pos_appointment", "module_pos_sms",
            "customer_display_bg_img", "customer_display_bg_img_name",
            "last_data_change", "create_date", "write_date",
        ]
        # pos_sale adds these relations to pos.config and its POS frontend
        # reads config.default_product_id while rendering order lines.
        fields_to_load.extend(
            field_name
            for field_name in ("default_product_id", "down_payment_product_id")
            if field_name in self._fields
        )
        if "ka_multi_uom" in self._fields:
            fields_to_load.append("ka_multi_uom")
        if "not_print_qr_url" in self._fields:
            fields_to_load.append("not_print_qr_url")
        return fields_to_load


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_not_print_qr_url = fields.Boolean(related="pos_config_id.not_print_qr_url", readonly=False)

