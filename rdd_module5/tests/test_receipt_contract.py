from odoo.tests.common import TransactionCase


class TestReceiptContract(TransactionCase):

    def test_qr_setting_is_preserved_and_exported_to_pos_session(self):
        config_model = self.env["pos.config"]
        self.assertIn("not_print_qr_url", config_model._fields)
        self.assertIn("is_not_print_qr_url", self.env["res.config.settings"]._fields)
        fields = config_model._load_pos_data_fields(self.env["pos.config"])
        self.assertIn("not_print_qr_url", fields)
        self.assertIn("use_pricelist", fields)
        # pos_sale's frontend dereferences config.default_product_id.id when
        # rendering POS order lines, so this relation must be in the config
        # payload even though the field is contributed by another addon.
        self.assertIn("default_product_id", fields)
        self.assertIn("down_payment_product_id", fields)

    def test_receipt_patch_obeys_qr_setting_without_replacing_other_receipt_data(self):
        from pathlib import Path
        addon = Path(__file__).parents[1]
        manifest = (addon / "__manifest__.py").read_text()
        receipt_view = (addon / "views/pos_receipt_templates.xml").read_text()
        self.assertIn("views/pos_receipt_templates.xml", manifest)
        self.assertNotIn("static/src/xml/pos_receipt.xml", manifest)
        self.assertNotIn("static/src/js/pos_order_qr_patch.js", manifest)
        self.assertIn('inherit_id="point_of_sale.pos_order_receipt"', receipt_view)
        self.assertIn("config['not_print_qr_url']", receipt_view)
