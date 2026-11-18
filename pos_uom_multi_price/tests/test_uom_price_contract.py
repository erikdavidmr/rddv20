from odoo.tests.common import TransactionCase


class TestUomPriceContract(TransactionCase):

    def test_uom_selector_import_uses_the_odoo_20_dialog_module(self):
        from pathlib import Path
        source = (Path(__file__).parents[1] / "static/src/app/product_screen/order_summary/order_summary.js").read_text()
        self.assertIn("@point_of_sale/app/utils/make_awaitable_dialog", source)
        self.assertIn("@point_of_sale/app/components/popups/selection_popup/selection_popup", source)
        self.assertNotIn("@point_of_sale/app/store/make_awaitable_dialog", source)

    def test_uom_button_uses_the_orderline_slot_rendered_in_odoo_20(self):
        from pathlib import Path
        addon = Path(__file__).parents[1]
        parent_template = (addon / "static/src/overrides/components/Screens/ProductScreen/ProductScreen.xml").read_text()
        orderline_template = (addon / "static/src/overrides/components/Screens/orderline/Orderline.xml").read_text()
        self.assertIn('t-set-slot="uom-multi-price"', parent_template)
        self.assertIn("this.pos.config.ka_multi_uom", parent_template)
        self.assertNotIn("pos.config.ka_multi_uom", parent_template.replace("this.pos.config.ka_multi_uom", ""))
        self.assertIn("//span[hasclass('text-wrap')]", orderline_template)
        self.assertIn('t-call-slot="uom-multi-price"', orderline_template)

    def test_pos_loader_accepts_the_odoo_20_config_record(self):
        config = self.env["pos.config"].search([], limit=1)
        self.assertTrue(config, "The isolated POS test database must contain a POS config")
        config.ka_multi_uom = True

        models = self.env["pos.session"]._load_pos_data_models(config)

        self.assertIn("product.multi.uom.price", models)

    def test_multi_uom_price_scales_from_product_reference_uom(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        product = self.env["product.template"].create({
            "name": "Multi UOM price regression",
            "list_price": 100.0,
        })
        price = self.env["product.multi.uom.price"].create({
            "product_id": product.id,
            "uom_id": dozen.id,
            "name": "Dozen",
        })
        self.assertAlmostEqual(price.price, product.list_price * dozen.factor, places=2)
        self.assertIn("uom_id", self.env["pos.order.line"]._fields)
        self.assertIn("multi_uom_price_ids", self.env["product.product"]._fields)

    def test_product_uom_pair_must_be_unique(self):
        product = self.env["product.template"].create({
            "name": "Multi UOM uniqueness regression",
            "list_price": 25.0,
        })
        values = {"product_id": product.id, "uom_id": product.uom_id.id}
        self.env["product.multi.uom.price"].create(values)
        self.cr.execute("""
            SELECT conname
              FROM pg_constraint
             WHERE conrelid = 'product_multi_uom_price'::regclass
               AND contype = 'u'
        """)
        constraints = {row[0] for row in self.cr.fetchall()}
        self.assertIn(
            "product_multi_uom_price_constraint_product_multi_uom_price_uniq",
            constraints,
        )
