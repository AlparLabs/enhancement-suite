from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _compute_price_unit_and_date_planned_and_name(self):
        """Preserve existing/manual date_planned on purchase order lines.

        Standard Odoo recalculates date_planned whenever product_qty, product_uom,
        company_id, or partner_id changes if a seller exists. This override
        ensures that if date_planned is already set on the line, it is preserved
        rather than overwritten by the vendor lead time calculation.
        """
        existing_dates = {line: line.date_planned for line in self if line.date_planned}
        super()._compute_price_unit_and_date_planned_and_name()
        for line, prev_date in existing_dates.items():
            if prev_date:
                line.date_planned = prev_date
