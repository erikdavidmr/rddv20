from odoo.tests.common import TransactionCase, new_test_user


class TestPricelistDaysAccess(TransactionCase):

    def test_internal_user_can_manage_pricelist_days(self):
        user = new_test_user(self.env, "rdd_pricelist_days_user", groups="base.group_user")
        days = self.env["pricelist.dias"].with_user(user)

        day = days.create({"nombre": "Migration access test", "day": "lunes"})
        self.assertEqual(days.browse(day.id).nombre, "Migration access test")
        day.write({"nombre": "Migration access updated"})
        self.assertEqual(day.nombre, "Migration access updated")
        day.unlink()
