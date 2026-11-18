from pathlib import Path

from odoo.tests.common import TransactionCase


class TestZeroQuantityContract(TransactionCase):

    def test_payment_screen_patch_is_in_pos_asset_bundle_and_has_block_message(self):
        manifest_path = Path(__file__).parents[1] / "__manifest__.py"
        source_path = Path(__file__).parents[1] / "static/src/js/pos_payment_validation.js"
        manifest = manifest_path.read_text()
        source = source_path.read_text()
        self.assertIn("point_of_sale._assets_pos", manifest)
        self.assertIn("pos_payment_validation.js", manifest)
        self.assertIn("this.pos.getOrder()", source)
        self.assertIn("getOrderlines()", source)
        self.assertIn("getQuantity() === 0", source)
        self.assertNotIn("get_order()", source)
        self.assertNotIn("get_orderlines()", source)
        self.assertNotIn("get_quantity()", source)
        self.assertIn("AlertDialog", source)
