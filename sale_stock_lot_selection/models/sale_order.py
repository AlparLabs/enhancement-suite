from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        moves = self.order_line.filtered('requested_lot_ids').move_ids.filtered(
            lambda m: m.state in ('confirmed', 'partially_available'))
        if moves:
            moves._action_assign()
        return res
