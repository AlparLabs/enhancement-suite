from __future__ import annotations

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_view_cost_schedules(self) -> dict:
        self.ensure_one()
        return self.product_tmpl_id.action_view_cost_schedules()

    def action_view_cost_history(self) -> dict:
        self.ensure_one()
        return self.product_tmpl_id.action_view_cost_history()
