from __future__ import annotations

from typing import Any

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PartnerObjective(models.Model):
    _name = 'partner.objective'
    _description = 'Partner Objective'
    _order = 'date desc, id desc'
    _check_company_auto = True

    date: fields.Date = fields.Date(
        string='Date / Period',
        required=True,
        default=fields.Date.context_today,
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
        string='Objective (Qty)',
        digits='Product Unit of Measure',
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
                raise ValidationError(_("Objective (Qty) cannot be negative."))
            if not record.objective and not record.objective_qty:
                raise ValidationError(_("At least one objective (amount or quantity) must be set."))

    @api.onchange('partner_id')
    def _onchange_partner_id(self) -> None:
        self.delivery_address_id = False
