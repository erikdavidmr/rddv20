from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    puc_field = fields.Monetary(
        string="Puc",
        store=True,
        currency_field='currency_id',
    )

    puc_multicompany = fields.Float(
        string="Puc multicompany",
        digits='Product Price',
        company_dependent=True  # Específico por empresa
    )

    puc_edit = fields.Boolean(
        string="Editar PUC general",
    )
    puc_multicompany_edit = fields.Boolean(
        string="Editar PUC por empresa",
        company_dependent=True  # También específico por empresa
    )

    def get_puc_value(self):
        """
        3 últimas órdenes confirmadas (date_approve) que incluyan el producto.
        Toma 1 línea por orden (la de mayor costo unitario) y luego el MAX entre esas 3.
        """
        company = self.env.company

        def uom_reference(uom):
            while uom.relative_uom_id:
                uom = uom.relative_uom_id
            return uom

        PurchaseOrder = self.env['purchase.order'].sudo()
        POL = self.env['purchase.order.line'].sudo()

        for record in self.sudo().with_company(company).with_context(force_company=company.id):

            # Si está editado manualmente (global o por empresa), no tocarlo
            if record.puc_edit or record.puc_multicompany_edit:
                _logger.info(
                    "[PUC] SKIP %s (company=%s) puc_edit=%s puc_multicompany_edit=%s",
                    record.display_name, company.display_name, record.puc_edit, record.puc_multicompany_edit
                )
                continue

            variant_ids = record.product_variant_ids.ids

            last_orders = PurchaseOrder.search([
                ('state', 'in', ['purchase', 'done']),
                ('company_id', '=', company.id),
                ('date_approve', '!=', False),
                ('order_line.product_id', 'in', variant_ids),
            ], order="date_approve desc, id desc", limit=3)

            _logger.info(
                "[PUC] %s (company=%s) last_orders=%s",
                record.display_name, company.display_name,
                [(po.name, po.id, po.date_approve, po.state) for po in last_orders]
            )

            if not last_orders:
                continue

            chosen_lines = POL.browse()
            for po in last_orders:
                lines = po.order_line.filtered(
                    lambda l: l.product_id.id in variant_ids
                              and l.product_qty and l.product_qty > 0
                              and l.product_uom and l.product_uom.factor
                              and record.uom_id and record.uom_id.factor
                              and uom_reference(l.product_uom) == uom_reference(record.uom_id)
                )
                if not lines:
                    _logger.info("[PUC] PO %s sin líneas válidas para %s", po.name, record.display_name)
                    continue

                def _unit_cost_in_base(l):
                    # Odoo 20 factor is the number of reference units per selected UoM.
                    return (l.price_subtotal / l.product_qty) / l.product_uom.factor

                best_line = max(lines, key=_unit_cost_in_base)
                chosen_lines |= best_line

                _logger.info(
                    "[PUC] PO %s best_line id=%s subtotal=%s qty=%s uom=%s uom.factor=%s -> unit_base=%s",
                    po.name, best_line.id, best_line.price_subtotal, best_line.product_qty,
                    best_line.product_uom.display_name, best_line.product_uom.factor,
                    _unit_cost_in_base(best_line)
                )

            if not chosen_lines:
                continue

            puc_unitario = max(
                ((l.price_subtotal / l.product_qty) / l.product_uom.factor)
                for l in chosen_lines
            )

            record.puc_multicompany = puc_unitario * record.uom_id.factor

            _logger.info(
                "[PUC] SET %s (company=%s) puc_unit_base=%s uom.factor=%s -> puc_multicompany=%s",
                record.display_name, company.display_name, puc_unitario,
                record.uom_id.factor, record.puc_multicompany
            )

    puc_group = fields.Boolean(
        string='Permiso PUC',
        compute="_compute_puc_group",
        help="Indica si el usuario tiene permiso para editar PUC"
    )

    @api.depends_context('uid')
    def _compute_puc_group(self):
        for record in self:
            record.puc_group = self.env.user.has_group('rdd_module.rdd_product_puc_group')

    def _price_compute(self, price_type, uom=None, currency=None, company=None, date=False):
        if price_type == 'standard_price':
            company = company or self.env.company
            self = self.with_company(company)
            prices = dict.fromkeys(self.ids, 0.0)

            for product in self:
                product_company = product.with_company(company)
                # usar PUC si existe, y si no, el costo con sudo
                if product_company.puc_multicompany:
                    price = product_company.puc_multicompany
                else:
                    price = product_company.sudo().standard_price

                price_currency = product.cost_currency_id

                if uom:
                    price = product.uom_id._compute_price(price, uom)
                if currency:
                    price = price_currency._convert(
                        price, currency, company,
                        date or fields.Date.context_today(self)
                    )

                prices[product.id] = price
            return prices

        return super()._price_compute(price_type, uom, currency, company, date)

    def migrar_puc(self):
        """Si quieres inicializar el PUC por empresa desde el campo global."""
        company = self.env.company
        for record in self.with_company(company):
            record.puc_multicompany = record.puc_field

    @api.model
    def cron_update_puc_all_companies(self):
        """Recalcula PUC por empresa con contexto correcto de multicompañía."""
        companies = self.env['res.company'].sudo().search([])
        for company in companies:
            env_pt = self.sudo().with_company(company).with_context(
                allowed_company_ids=[company.id],
                company_id=company.id,
                force_company=company.id,  # <-- CLAVE para fields company_dependent (ir.property)
            )
            env_pt.search([]).get_puc_value()

class ProductProductInherit(models.Model):
    _inherit = 'product.product'

    puc_field = fields.Monetary(
        string="PUC",
        compute="_compute_puc_field",
        inverse="_inverse_puc_field",
        currency_field='currency_id'
    )

    puc_multicompany = fields.Float(
        string="PUC (por empresa)",
        related='product_tmpl_id.puc_multicompany',
        readonly=False,
        digits='Product Price',
    )

    puc_multicompany_edit = fields.Boolean(
        string="Editar PUC por empresa",
        related="product_tmpl_id.puc_multicompany_edit",
        readonly=False,
    )
    puc_edit = fields.Boolean(
        string="Editar PUC general",
        related="product_tmpl_id.puc_edit",
        readonly=False,
    )

    @api.depends('product_tmpl_id.puc_field')
    def _compute_puc_field(self):
        for product in self:
            product.puc_field = product.product_tmpl_id.puc_field

    def _inverse_puc_field(self):
        for product in self:
            product.product_tmpl_id.puc_field = product.puc_field

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if 'puc_multicompany' not in fields_list:
            fields_list.append('puc_multicompany')
        return fields_list

    def _load_pos_data(self, data):
        result = super()._load_pos_data(data)

        # Asegurar que puc_multicompany tiene un valor por defecto si no está presente
        if 'product.product' in result:
            for product in result['product.product']['data']:
                if 'puc_multicompany' not in product:
                    product['puc_multicompany'] = 0.0

        return result

    def _price_compute(self, price_type, uom=None, currency=None, company=None, date=False):
        if price_type == 'standard_price':
            company = company or self.env.company
            self = self.with_company(company)
            prices = dict.fromkeys(self.ids, 0.0)

            for product in self:
                product_company = product.with_company(company)

                if product_company.puc_multicompany:
                    price = product_company.puc_multicompany
                else:
                    # leer standard_price con sudo para evitar el AccessError
                    price = product_company.sudo().standard_price

                price_currency = product.cost_currency_id

                if uom:
                    price = product.uom_id._compute_price(price, uom)
                if currency:
                    price = price_currency._convert(
                        price, currency, company,
                        date or fields.Date.context_today(self)
                    )

                prices[product.id] = price
            return prices

        return super()._price_compute(price_type, uom, currency, company, date)
