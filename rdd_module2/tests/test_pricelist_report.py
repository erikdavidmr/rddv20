from odoo.tests.common import TransactionCase


class TestPricelistReportWithTax(TransactionCase):

    def test_html_report_price_includes_product_tax_for_each_uom_quantity(self):
        tax_group = self.env["account.tax.group"].create({
            "name": "RDD report tax group",
            "company_id": self.env.company.id,
        })
        tax = self.env["account.tax"].create({
            "name": "RDD report 16 percent",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "tax_group_id": tax_group.id,
            "company_id": self.env.company.id,
            "country_id": self.env.ref("base.mx").id,
        })
        product = self.env["product.product"].create({
            "name": "RDD report taxable product",
            "list_price": 100,
            "taxes_id": [(6, 0, tax.ids)],
        })
        pricelist = self.env["product.pricelist"].create({
            "name": "RDD report test pricelist",
            "currency_id": self.env.company.currency_id.id,
        })

        report = self.env["report.product.report_pricelist"]
        data = {
            "active_model": "product.product",
            "active_ids": product.ids,
            "pricelist_id": pricelist.id,
            "quantities": [1],
        }
        values = report._get_report_data(data)

        product_data = values["products"][0]
        self.assertAlmostEqual(
            product_data["price"][product.uom_id.id][1],
            116.0,
            places=2,
        )
        self.assertIn(product.name, str(report.get_html(data)))
