from __future__ import annotations

from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    replacement_cost_unit = fields.Float(
        string='Costo de reposición',
        compute='_compute_replacement_cost_unit',
        store=True,
        min_display_digits='Product Price',
        help='Costo de reposición unitario a la fecha de la venta.',
    )
    replacement_margin = fields.Monetary(
        string='Margen de reposición',
        compute='_compute_replacement_margin',
        store=True,
    )

    @api.depends('product_id', 'order_id.company_id', 'order_id.currency_id')
    def _compute_replacement_cost_unit(self) -> None:
        for line in self:
            order = line.order_id
            if not line.product_id or line.product_id.type == 'combo' or not order:
                line.replacement_cost_unit = 0.0
                continue
            company = order.company_id
            cost, _is_fallback = line.product_id._get_replacement_cost_for(
                company,
                line.product_id.uom_id,
                order.currency_id or company.currency_id,
                fields.Date.to_date(order.date_order or fields.Datetime.now()),
            )
            line.replacement_cost_unit = cost

    @api.depends('price_subtotal', 'qty', 'replacement_cost_unit')
    def _compute_replacement_margin(self) -> None:
        for line in self:
            line.replacement_margin = line.price_subtotal - line.replacement_cost_unit * line.qty


class PosOrder(models.Model):
    _inherit = 'pos.order'

    replacement_margin = fields.Monetary(
        string='Margen de reposición',
        compute='_compute_replacement_margin',
        store=True,
    )

    @api.depends('lines.replacement_margin')
    def _compute_replacement_margin(self) -> None:
        for order in self:
            order.replacement_margin = sum(order.lines.mapped('replacement_margin'))
