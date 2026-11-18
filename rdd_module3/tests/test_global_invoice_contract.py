from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestGlobalInvoiceContract(TransactionCase):

    def test_global_invoice_fields_remain_available(self):
        expected = {
            "pos.order": {"global_invoice_id", "l10n_mx_edi_payment_method_id"},
            "account.move": {
                "pos_order_count", "config_id", "x_is_global_pdv",
                "x_global_periodicity", "x_global_period_date", "x_cfdi_emission_datetime",
            },
            "l10n_mx_edi.invoice.cancel": {
                "replacement_global_period_date", "replacement_payment_term_id",
                "replacement_payment_way_id", "replacement_emission_datetime",
                "has_substitution_doc",
            },
            "l10n_mx_edi.global_invoice.create": {"pos_order_ids", "emission_datetime", "global_period_date"},
        }
        for model, field_names in expected.items():
            self.assertTrue(field_names <= set(self.env[model]._fields), model)

    def test_forced_replacement_datetime_enforces_72_hour_window(self):
        wizard = self.env["l10n_mx_edi.invoice.cancel"].new({})
        now = fields.Datetime.now()
        wizard._validate_forced_datetime(now - timedelta(hours=72))
        with self.assertRaises(UserError):
            wizard._validate_forced_datetime(now - timedelta(hours=73))
        with self.assertRaises(UserError):
            wizard._validate_forced_datetime(now + timedelta(minutes=1))
