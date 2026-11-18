# -*- coding: utf-8 -*-

from odoo import models, fields

class StockPicking(models.Model):
    _inherit='stock.picking'

    def _prepare_stock_move_vals(self, first_line, order_lines):
        res = super(StockPicking, self)._prepare_stock_move_vals(first_line, order_lines)
        res['product_uom'] = first_line.uom_id.id or first_line.product_id.uom_id.id,
        return res
    
    def _create_move_from_pos_order_lines(self, lines):
        # Remove group by product_id from the lines
        self.ensure_one()
        move_vals = []
        for olines in sorted(lines, key=lambda l: l.product_id.id):
            order_lines = self.env['pos.order.line'].concat(*olines)
            move_vals.append(self._prepare_stock_move_vals(order_lines[0], order_lines))
        moves = self.env['stock.move'].create(move_vals)
        confirmed_moves = moves._action_confirm()
        confirmed_moves._add_mls_related_to_order(lines, are_qties_done=True)
        confirmed_moves.picked = True
        self._link_owner_on_return_picking(lines)
