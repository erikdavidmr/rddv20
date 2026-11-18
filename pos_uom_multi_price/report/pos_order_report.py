# -*- coding: utf-8 -*-

from odoo import models
from odoo.tools import SQL


class PosOrderReport(models.Model):
    _inherit='report.pos.order'

    def _from(self):
        original_query = super()._from()

        code, params, to_flush = original_query._sql_tuple
        modified_query = code.replace(
            "LEFT JOIN uom_uom u ON (u.id=pt.uom_id)",
            "LEFT JOIN uom_uom u ON (u.id=l.uom_id)"
        )
        return SQL(modified_query, *params, to_flush=to_flush)
