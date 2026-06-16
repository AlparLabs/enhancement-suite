from __future__ import annotations

from datetime import timedelta
from typing import Any

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PartnerObjective(models.Model):
    _name = 'partner.objective'
    _description = 'Partner Objective'
    _order = 'date desc, id desc'
    _check_company_auto = True

    date: fields.Date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    date_end: fields.Date = fields.Date(
        string='End Date',
        index=True,
    )
    partner_id: models.Model = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        required=True,
        index=True,
        ondelete='cascade',
        check_company=True,
    )
    delivery_address_id: models.Model = fields.Many2one(
        comodel_name='res.partner',
        string='Delivery Address',
        domain="[('type', '=', 'delivery'), ('parent_id', '=', partner_id)]",
        index=True,
        check_company=True,
    )
    objective: float = fields.Monetary(
        string='Objective (Amount)',
        currency_field='currency_id',
    )
    objective_qty: float = fields.Float(
        string='Objective (Dozens)',
        digits='Product Unit of Measure',
        help="Target number of dozens the partner should buy in the period.",
    )
    dozens_sold: float = fields.Float(
        string='Dozens Sold (Period)',
        compute='_compute_dozens_sold',
        digits='Product Unit of Measure',
        help=(
            "Total dozens sold to the partner within the objective period, "
            "based on confirmed sale orders. Each line contributes its sold "
            "quantity multiplied by the product's 'Dozens per Unit', and only "
            "products flagged 'Counts for Objectives' are included."
        ),
    )
    dozens_remaining: float = fields.Float(
        string='Dozens Remaining',
        compute='_compute_dozens_achievement',
        digits='Product Unit of Measure',
        help="Dozens still missing to reach the objective (0 once met).",
    )
    dozens_achievement_pct: float = fields.Float(
        string='Achievement (%)',
        compute='_compute_dozens_achievement',
        help="Dozens sold as a percentage of the dozens objective.",
    )
    dozens_achieved: bool = fields.Boolean(
        string='Objective Met',
        compute='_compute_dozens_achievement',
        help="Set once the dozens sold reach or exceed the objective.",
    )
    currency_id: models.Model = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id: models.Model = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.constrains('objective', 'objective_qty')
    def _check_objective(self) -> None:
        for record in self:
            if record.objective < 0:
                raise ValidationError(_("Objective (Amount) cannot be negative."))
            if record.objective_qty < 0:
                raise ValidationError(_("Objective (Dozens) cannot be negative."))
            if not record.objective and not record.objective_qty:
                raise ValidationError(_("At least one objective (amount or dozens) must be set."))

    @api.constrains('date', 'date_end')
    def _check_dates(self) -> None:
        for record in self:
            if record.date_end and record.date_end < record.date:
                raise ValidationError(_("End Date cannot be earlier than Start Date."))

    @api.depends('date', 'date_end', 'partner_id', 'delivery_address_id')
    def _compute_dozens_sold(self) -> None:
        for record in self:
            record.dozens_sold = record._get_dozens_sold()

    @api.depends('dozens_sold', 'objective_qty')
    def _compute_dozens_achievement(self) -> None:
        for record in self:
            target = record.objective_qty
            sold = record.dozens_sold
            record.dozens_remaining = max(target - sold, 0.0)
            record.dozens_achievement_pct = (sold / target * 100) if target else 0.0
            record.dozens_achieved = bool(target) and sold >= target

    def _get_dozens_sold(self) -> float:
        """Sum dozens sold to the partner through confirmed sale orders in the period.

        Each sale order line contributes ``qty * product.objective_dozen_qty``
        dozens, counting only products flagged ``counts_for_objective``.
        """
        self.ensure_one()
        if not self.partner_id or not self.date:
            return 0.0

        domain = [
            ('order_id.state', 'in', ('sale', 'done')),
            ('order_id.partner_id', 'child_of', self.partner_id.id),
            ('order_id.date_order', '>=', fields.Datetime.to_datetime(self.date)),
            ('product_id.counts_for_objective', '=', True),
            ('product_id.objective_dozen_qty', '!=', 0.0),
        ]
        if self.date_end:
            end = fields.Datetime.to_datetime(self.date_end) + timedelta(days=1)
            domain.append(('order_id.date_order', '<', end))
        if self.delivery_address_id:
            domain.append(('order_id.partner_shipping_id', '=', self.delivery_address_id.id))

        lines = self.env['sale.order.line'].search(domain)
        return sum(
            line.product_uom_qty * line.product_id.objective_dozen_qty
            for line in lines
        )

    @api.onchange('partner_id')
    def _onchange_partner_id(self) -> None:
        self.delivery_address_id = False
