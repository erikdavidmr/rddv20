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

    def test_manager_approval_access_is_granted_to_pos_users(self):
        pos_user_group = self.env.ref("point_of_sale.group_pos_user")
        access_ids = (
            "access_pos_manager_approval_m",
            "access_pos_manager_approval_u",
        )
        for access_id in access_ids:
            access = self.env.ref(
                f"pos_restaurant_restiction_and_validation.{access_id}"
            )
            self.assertEqual(access.model_id.model, "manager.approval")
            self.assertEqual(access.group_id, pos_user_group)
            self.assertEqual(access.operation, "crud")

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

    def test_manager_approval_uses_odoo_20_employee_roles_and_hashed_pins(self):
        addon = Path(__file__).parents[1]
        active_scripts = (
            "static/src/app/decrease_quantity_by_manager.js",
            "static/src/app/delete_by_manager.js",
            "static/src/app/session_close_by_manager.js",
        )
        for relative_path in active_scripts:
            source = (addon / relative_path).read_text()
            self.assertNotIn("advanced_employee_ids", source, relative_path)

        for relative_path in active_scripts:
            source = (addon / relative_path).read_text()
            self.assertIn('models["hr.employee"].getAll()', source, relative_path)
            self.assertNotIn("manager_employee_ids", source, relative_path)
            self.assertIn('employee._role === "manager"', source, relative_path)
            pin_check = "Sha1.hash(this.state.pin)" if relative_path == active_scripts[2] else "Sha1.hash(payload)"
            self.assertIn(pin_check, source, relative_path)
        self.assertIn("cashier?._role !== 'cashier'", (addon / active_scripts[0]).read_text())
        self.assertIn("cashier._role === 'cashier'", (addon / active_scripts[1]).read_text())
        source = (addon / active_scripts[2]).read_text()
        self.assertNotIn('"pin"', source)

    def test_authorization_popup_declares_owl_3_props_schema(self):
        addon = Path(__file__).parents[1]
        source = (addon / "static/src/screens/popUps/deny_popUp.js").read_text()
        self.assertIn('import { Component, useProps, t } from "@odoo/owl";', source)
        self.assertIn("props = useProps({", source)
        self.assertIn("confirmText: t.string().optional(", source)
        self.assertIn("body: t.string().optional(", source)
        self.assertIn("getPayload: t.function()", source)
        self.assertIn("close: t.function()", source)
        self.assertNotIn("static defaultProps", source)
        template = (addon / "static/src/screens/popUps/deny_popUp.xml").read_text()
        self.assertIn('title="this.props.title"', template)
        self.assertIn('t-esc="this.props.body"', template)
        self.assertNotIn('props.title', template.replace('this.props.title', ''))

    def test_session_authorization_dialog_uses_owl_3_props_and_template_context(self):
        addon = Path(__file__).parents[1]
        source = (addon / "static/src/app/session_close_by_manager.js").read_text()
        self.assertIn("import { Component, proxy, useProps, t, xml } from \"@odoo/owl\";", source)
        self.assertNotIn("static props =", source)
        self.assertIn("props = useProps({", source)
        self.assertIn('this.props.managers', source)
        self.assertIn('t-model.proxy="this.state.pin"', source)

    def test_cashiers_can_reach_manager_gated_session_close(self):
        addon = Path(__file__).parents[1]
        source = (addon / "static/src/app/session_close_by_manager.js").read_text()
        self.assertIn(
            'import { PosAccessRightPlugin } from "@point_of_sale/app/plugins/access_right_plugin";',
            source,
        )
        self.assertIn("get canCloseSession()", source)
        self.assertIn("this.config.enable_restriction_on_session_close", source)
        self.assertIn('this.hasEmployeeRole(["cashier", "manager"])', source)

    def test_session_close_restriction_flag_is_loaded_into_pos_config(self):
        fields = self.env["pos.config"]._load_pos_data_fields(self.env["pos.config"])
        self.assertIn("enable_restriction_on_session_close", fields)

    def test_rdd_close_popup_template_uses_owl_3_component_context(self):
        addon_root = Path(__file__).parents[2]
        template = (
            addon_root / "rdd_module/static/src/app/navbar/closing_popup/closing_popup.xml"
        ).read_text()
        for legacy_expression in (
            't-if="pos.config.',
            't-if="props.',
            't-esc="props.',
            't-model="state.',
            't-on-click="confirm"',
            't-on-click="cancel"',
            't-on-click="openDetailsPopup"',
        ):
            self.assertNotIn(legacy_expression, template)
        self.assertIn('t-if="this.pos.config.cash_control"', template)
        self.assertIn('t-if="this.props.opening_notes"', template)
        self.assertIn('t-model.proxy="this.state.notes"', template)

    def test_session_close_audit_uses_odoo_20_active_cashier(self):
        source = (
            Path(__file__).parents[1]
            / "static/src/app/session_close_by_manager.js"
        ).read_text()
        self.assertIn("const cashier = this.pos.accessRight.cashier", source)
        self.assertIn("cashier1: cashier.id", source)
        self.assertNotIn("this.pos.cashier.id", source)
        self.assertNotIn("this.pos.cashier?.name", source)
        self.assertIn("const approvalRegistered = await this.registerManagerApproval", source)
        self.assertIn("if (!approvalRegistered)", source)
