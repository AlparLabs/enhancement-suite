from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _compute_price_unit_and_date_planned_and_name(self):
        """Preserve existing/manual date_planned on purchase order lines,
        and default new lines to the order's date_planned if already set.

        Standard Odoo recalculates date_planned whenever product_qty, product_uom,
        company_id, or partner_id changes if a seller exists. This override
        ensures that:
        1. If date_planned is already set on the line, it is preserved rather
           than overwritten by vendor lead time.
        2. If adding a new line to an order that already has an expected arrival
           date (order_id.date_planned), the new line inherits that date instead
           of resetting the order's date back to today + lead time.
        """
        preserved_dates = {}
        for line in self:
            if line.date_planned:
                preserved_dates[line] = line.date_planned
            elif line.order_id.date_planned:
                preserved_dates[line] = line.order_id.date_planned

        super()._compute_price_unit_and_date_planned_and_name()

        for line, date_planned in preserved_dates.items():
            if date_planned:
                line.date_planned = date_planned
