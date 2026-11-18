from odoo import models, api

class ReportProductPricelist(models.AbstractModel):
    _inherit = 'report.product.report_pricelist'

    @api.model
    def _get_report_data(self, data, report_type='html'):
        res = super()._get_report_data(data, report_type)

        partner = self.env.user.partner_id
        company = self.env.company
        
        pricelist = res.get("pricelist")
        if not pricelist:
            return res
            
        currency = pricelist.currency_id

        def compute_tax_in_place(product_dict):
            product_record = self.env["product.product"].browse(product_dict["id"])
            taxes = product_record.taxes_id.filtered(lambda tax: tax.company_id == company)
            if not taxes:
                return
            # Odoo 20 structures prices as {uom_id: {quantity: unit_price}}.
            # Compute each unit price at its requested quantity, keeping that shape
            # for the shared HTML and PDF report templates.
            for prices_by_quantity in product_dict.get("price", {}).values():
                for quantity, base_price in list(prices_by_quantity.items()):
                    tax_res = taxes.compute_all(
                        base_price,
                        currency,
                        quantity,
                        product=product_record,
                        partner=partner,
                    )
                    prices_by_quantity[quantity] = (
                        tax_res["total_included"] / quantity if quantity else base_price
                    )

        for product in res.get("products", []):
            compute_tax_in_place(product)
            for variant in product.get("variants", []):
                compute_tax_in_place(variant)

        return res
