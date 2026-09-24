from __future__ import annotations

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    replacement_margin = fields.Monetary(
        string='Margen de reposición',
        compute='_compute_replacement_margin',
        store=True,
        groups='base.group_user',
    )
    replacement_margin_percent = fields.Float(
        string='Margen de reposición (%)',
        compute='_compute_replacement_margin',
        store=True,
        aggregator='avg',
        groups='base.group_user',
    )

    @api.depends('order_line.replacement_margin', 'amount_untaxed')
    def _compute_replacement_margin(self) -> None:
        for order in self:
            order.replacement_margin = sum(order.order_line.mapped('replacement_margin'))
            order.replacement_margin_percent = (
                order.amount_untaxed and order.replacement_margin / order.amount_untaxed
            )

    def action_confirm(self):
        # Un presupuesto puede quedar semanas abierto: con inflación, el costo que
        # importa es el del día de la venta.
        self.order_line.filtered('product_id')._refresh_replacement_cost()
        return super().action_confirm()
