from odoo.tests.common import TransactionCase
from pathlib import Path


class TestManagerApprovalContract(TransactionCase):

    def test_restriction_settings_and_audit_fields_remain_available(self):
        config_fields = {
            "enable_pos_restaurant_restiction", "enable_restriction_on_orderline_delete",
            "enable_restriction_on_order_delete", "enable_restriction_on_session_close",
        }
        self.assertTrue(config_fields <= set(self.env["pos.config"]._fields))
        audit_fields = {"session_id", "manager_approved", "cashier", "state", "receipt_number", "order_number"}
        self.assertTrue(audit_fields <= set(self.env["manager.approval"]._fields))
        setting_fields = {
            "is_pos_restaurant_restiction", "is_restriction_on_orderline_delete",
            "is_restriction_on_order_delete", "is_restriction_on_session_close",
        }
        self.assertTrue(setting_fields <= set(self.env["res.config.settings"]._fields))

    def test_pos_scripts_import_the_odoo_20_component_modules(self):
        addon = Path(__file__).parents[1]
        expected = {
            "static/src/app/decrease_quantity_by_manager.js": (
                "@point_of_sale/app/components/popups/number_popup/number_popup",
                "@point_of_sale/app/components/popups/selection_popup/selection_popup",
            ),
            "static/src/app/delete_by_manager.js": (
                "@point_of_sale/app/components/popups/number_popup/number_popup",
                "@point_of_sale/app/components/popups/selection_popup/selection_popup",
                "@point_of_sale/app/utils/make_awaitable_dialog",
            ),
            "static/src/app/session_close_by_manager.js": (
                "@point_of_sale/app/components/popups/closing_popup/closing_popup",
                "@point_of_sale/app/utils/make_awaitable_dialog",
            ),
        }
        for relative_path, imports in expected.items():
            source = (addon / relative_path).read_text()
            for module in imports:
                self.assertIn(module, source, f"{relative_path} must import {module}")

    def test_orderline_restrictions_use_odoo_20_pos_apis(self):
        addon = Path(__file__).parents[1]
        source = (addon / "static/src/app/decrease_quantity_by_manager.js").read_text()
        for api in ("this.pos.getOrder()", "getSelectedOrderline()", "getProduct()", "getOrderlines()"):
            self.assertIn(api, source)
        for legacy_api in ("get_order()", "get_selected_orderline()", "get_product()", "get_orderlines()"):
            self.assertNotIn(legacy_api, source)
