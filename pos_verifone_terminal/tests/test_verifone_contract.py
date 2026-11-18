from pathlib import Path

from odoo.tests.common import HttpCase, TransactionCase


class TestVerifoneContract(TransactionCase):

    def test_terminal_configuration_and_payment_fields_remain_available(self):
        self.assertTrue({"verifone_middleware_ip", "verifone_middleware_port"} <= set(self.env["pos.payment.method"]._fields))
        self.assertTrue({"verifone_payload_raw", "verifone_status", "verifone_card_type"} <= set(self.env["pos.payment"]._fields))

    def test_webhook_and_payment_status_routes_are_declared(self):
        source_root = Path(__file__).parents[1]
        self.assertIn("/verifone/webhook_pago", (source_root / "controllers/main.py").read_text())
        self.assertIn("/verifone/payment_status", (source_root / "controllers/payment_status.py").read_text())
        self.assertIn("verifone_middleware_ip", (source_root / "controllers/main.py").read_text())

    def test_payment_provider_uses_the_odoo_20_registry_and_interface(self):
        source_root = Path(__file__).parents[1] / "static/src"
        interface = (source_root / "app/payment_verifone.esm.js").read_text()
        registration = (source_root / "overrides/models/models.esm.js").read_text()
        self.assertIn("@point_of_sale/app/utils/payment/payment_interface", interface)
        self.assertIn("async sendPaymentRequest(pay_line)", interface)
        self.assertIn('pay_line.setPaymentStatus("waitingCard")', interface)
        self.assertIn('registry.category("pos_payment_providers").add("verifone_middleware"', registration)
        self.assertNotIn("register_payment_method", registration)


class TestVerifoneHttpRoutes(HttpCase):

    def test_payment_status_requires_a_reference(self):
        response = self.url_open("/verifone/payment_status")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "missing_reference")
