from __future__ import annotations

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    counts_for_objective: bool = fields.Boolean(
        string='Counts for Objectives',
        default=False,
        help="If set, this product is included when computing the dozens sold "
             "towards a partner's objective.",
    )
    objective_dozen_qty: float = fields.Float(
        string='Dozens per Unit',
        digits='Product Unit of Measure',
        help="How many dozens one unit of this product represents when "
             "computing dozens sold towards a partner's objective.",
    )
