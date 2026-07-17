from odoo import models
from odoo.tools import float_compare


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_assign(self, force_qty=False):
        if not force_qty:
            self._reserve_requested_lots()
        return super()._action_assign(force_qty=force_qty)

    def _reserve_requested_lots(self):
        """Reserve the salesperson-requested lots before the native
        reservation runs. Anything not covered here is handled by
        super()._action_assign() with the native removal strategy."""
        for move in self:
            requested_lots = move.sale_line_id.requested_lot_ids
            if not requested_lots:
                continue
            if move.picked or move.state not in ('confirmed', 'partially_available'):
                continue
            if move.move_orig_ids or move.procure_method == 'make_to_order':
                continue
            if move._should_bypass_reservation():
                continue
            if move.product_id.tracking != 'lot':
                continue
            move = move.with_company(move.company_id)
            rounding = move.product_id.uom_id.rounding
            missing = move.product_uom._compute_quantity(
                move.product_uom_qty - move.quantity,
                move.product_id.uom_id, rounding_method='HALF-UP')
            for requested in requested_lots:
                if float_compare(missing, 0, precision_rounding=rounding) <= 0:
                    break
                already_reserved = sum(
                    move.move_line_ids.filtered(
                        lambda ml, lot=requested.lot_id: ml.lot_id == lot
                    ).mapped('quantity_product_uom'))
                remaining = requested.quantity - already_reserved
                if float_compare(remaining, 0, precision_rounding=rounding) <= 0:
                    continue
                need = min(remaining, missing)
                taken = move._update_reserved_quantity(
                    need, move.location_id,
                    lot_id=requested.lot_id, strict=False)
                missing -= taken
