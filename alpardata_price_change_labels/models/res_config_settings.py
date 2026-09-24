from __future__ import annotations

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shelf_pricelist_id = fields.Many2one(
        related='company_id.shelf_pricelist_id', readonly=False,
    )
    markup_tolerance_pct = fields.Float(
        related='company_id.markup_tolerance_pct', readonly=False,
    )
