from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.rdd_module.models import pricelist as pricelist_module


class TestRddModuleMigrationContract(TransactionCase):

    def test_pos_assets_do_not_load_the_removed_order_receipt_component(self):
        manifest = (Path(__file__).parents[1] / "__manifest__.py").read_text()
        self.assertNotIn('"rdd_module/static/src/app/generic_components/orderline/*"', manifest)
        self.assertNotIn("'rdd_module/static/src/app/generic_components/orderline/*'", manifest)
        self.assertNotIn("rdd_module/static/src/app/generic_components/orderline/orderline.xml", manifest)

    def test_migrated_field_names_remain_available(self):
        expected_fields = {
            "product.template": {
                "puc_field",
                "puc_multicompany",
                "puc_edit",
                "puc_multicompany_edit",
                "puc_group",
            },
            "product.product": {"puc_field", "puc_multicompany"},
            "res.users": {"user_warehouse"},
            "product.pricelist": {
                "days_apply",
                "days_apply_m2m",
                "sales_team",
                "expire_date",
            },
            "product.pricelist.item": {"markup_rdd"},
            "pos.config": {"prefix", "suffix"},
        }
        for model_name, field_names in expected_fields.items():
            self.assertTrue(
                field_names <= set(self.env[model_name]._fields),
                f"Missing fields on {model_name}: {field_names - set(self.env[model_name]._fields)}",
            )

    def test_pos_product_loader_keeps_puc_and_standard_price_inputs(self):
        config = self.env["pos.config"].search([], limit=1)
        self.assertTrue(config, "The isolated POS test database must contain a POS config")
        fields = set(self.env["product.product"]._load_pos_data_fields(config))
        self.assertTrue({"puc_multicompany", "standard_price", "lst_price", "product_tmpl_id"} <= fields)

    def test_warehouse_restrictions_still_use_assigned_warehouses(self):
        expected_rules = {
            "access_limitacion_almacen_type_manager": "user.user_warehouse.ids",
            "access_limitacion_almacen_picking_manager": "user.user_warehouse.ids",
            "access_limitacion_almacen_quant_manager": "user.user_warehouse.ids",
        }
        for xmlid, expected_domain_part in expected_rules.items():
            rule = self.env.ref(f"rdd_module.{xmlid}")
            self.assertEqual(rule.model_id.model, {
                "access_limitacion_almacen_type_manager": "stock.picking.type",
                "access_limitacion_almacen_picking_manager": "stock.picking",
                "access_limitacion_almacen_quant_manager": "stock.quant",
            }[xmlid])
            self.assertIn(expected_domain_part, rule.domain)

    def test_puc_is_isolated_per_company_and_used_as_cost(self):
        company_a = self.env.company
        company_b = self.env["res.company"].create({
            "name": "RDD PUC Company B",
            "currency_id": company_a.currency_id.id,
        })
        template = self.env["product.template"].create({
            "name": "RDD Company Dependent PUC Test",
            "list_price": 100.0,
        })

        template.with_company(company_a).puc_multicompany = 12.5
        template.with_company(company_b).puc_multicompany = 38.75

        self.assertEqual(template.with_company(company_a).puc_multicompany, 12.5)
        self.assertEqual(template.with_company(company_b).puc_multicompany, 38.75)

        product = template.product_variant_id.with_company(company_a)
        costs = product._price_compute("standard_price", company=company_a)
        self.assertEqual(costs[product.id], 12.5)

    def test_markup_rdd_converts_margin_to_core_pricelist_discount(self):
        pricelist = self.env["product.pricelist"].create({
            "name": "RDD Markup Test",
            "currency_id": self.env.company.currency_id.id,
            "company_id": self.env.company.id,
        })
        rule = self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id,
            "applied_on": "3_global",
            "compute_price": "markup",
            "markup_rdd": 20.0,
        })
        self.assertAlmostEqual(rule.price_discount, -25.0)
        self.assertAlmostEqual(rule.price_markup, 25.0)

        rule.markup_rdd = 100.0
        self.assertAlmostEqual(rule.price_discount, 0.0)
        self.assertAlmostEqual(rule.price_markup, 0.0)

    def test_weekday_schedule_uses_selection_key_for_wednesday(self):
        team = self.env["crm.team"].create({"name": "RDD Wednesday Team"})
        pricelist = self.env["product.pricelist"].create({
            "name": "RDD Wednesday Schedule",
            "currency_id": self.env.company.currency_id.id,
            "company_id": self.env.company.id,
            "days_apply_m2m": [(0, 0, {"nombre": "Wednesday", "day": "miercoles"})],
            "sales_team": [(4, team.id)],
            "expire_date": fields.Datetime.to_datetime("2026-12-31 23:59:59"),
        })
        pos_config = SimpleNamespace(
            available_pricelist_ids=pricelist,
            pricelist_id=False,
        )

        class FrozenDateTime:
            @staticmethod
            def now():
                return datetime(2026, 11, 11, 12, 0, 0)

        with patch.object(pricelist_module, "datetime", FrozenDateTime), patch.object(
            type(pricelist), "correo_lista_precio_pos"
        ), patch.object(type(self.env["pos.config"]), "search", return_value=[pos_config]):
            pricelist.change_pricelist()

        self.assertEqual(pos_config.pricelist_id, pricelist.id)

    def test_pricelist_time_schedule_evaluates_shifts_correctly(self):
        team = self.env["crm.team"].create({"name": "RDD Shift Team"})
        dias_record = self.env["pricelist.dias"].create({"nombre": "Wednesday", "day": "miercoles"})

        pl_morning = self.env["product.pricelist"].create({
            "name": "Morning Shift Pricelist",
            "currency_id": self.env.company.currency_id.id,
            "company_id": self.env.company.id,
            "days_apply_m2m": [(4, dias_record.id)],
            "sales_team": [(4, team.id)],
            "use_time_schedule": True,
            "hour_from": 8.0,
            "hour_to": 14.0,
            "schedule_priority": 20,
            "notify_on_change": False,
        })
        pl_afternoon = self.env["product.pricelist"].create({
            "name": "Afternoon Shift Pricelist",
            "currency_id": self.env.company.currency_id.id,
            "company_id": self.env.company.id,
            "days_apply_m2m": [(4, dias_record.id)],
            "sales_team": [(4, team.id)],
            "use_time_schedule": True,
            "hour_from": 14.0,
            "hour_to": 21.0,
            "schedule_priority": 20,
            "notify_on_change": False,
        })

        all_pls = pl_morning | pl_afternoon
        pos_config = SimpleNamespace(
            name="Caja Test",
            crm_team_id=team,
            available_pricelist_ids=all_pls,
            pricelist_id=False,
            company_id=self.env.company,
        )

        class MorningTime:
            @staticmethod
            def now():
                # 2026-11-11 16:00:00 UTC is 10:00 AM in America/Mexico_City (UTC-6)
                return datetime(2026, 11, 11, 16, 0, 0)

        with patch.object(pricelist_module, "datetime", MorningTime), patch.object(
            type(self.env["pos.config"]), "search", return_value=[pos_config]
        ):
            all_pls.change_pricelist()

        self.assertEqual(pos_config.pricelist_id, pl_morning.id, "Morning shift pricelist must be selected at 10:00 AM local")

        class AfternoonTime:
            @staticmethod
            def now():
                # 2026-11-11 22:00:00 UTC is 16:00 (4:00 PM) in America/Mexico_City (UTC-6)
                return datetime(2026, 11, 11, 22, 0, 0)

        with patch.object(pricelist_module, "datetime", AfternoonTime), patch.object(
            type(self.env["pos.config"]), "search", return_value=[pos_config]
        ):
            all_pls.change_pricelist()

        self.assertEqual(pos_config.pricelist_id, pl_afternoon.id, "Afternoon shift pricelist must be selected at 16:00 local")

