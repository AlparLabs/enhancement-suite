from __future__ import annotations

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    objective_ids: models.Model = fields.One2many(
        comodel_name='partner.objective',
        inverse_name='partner_id',
        string='Objectives',
    )
    objective_count: int = fields.Integer(
        string='Objectives',
        compute='_compute_objective_count',
    )

    @api.depends('objective_ids')
    def _compute_objective_count(self) -> None:
        for partner in self:
            partner.objective_count = len(partner.objective_ids)
