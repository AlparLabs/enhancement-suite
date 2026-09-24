from __future__ import annotations

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    _commercial_condition_fields = ('internal_tax_pct', 'target_markup_pct')

    target_markup_pct = fields.Float(
        string='Recargo objetivo (%)',
        compute='_compute_target_markup_pct',
        store=True,
        readonly=False,
        precompute=True,
        help='Se toma de la categoría; se puede modificar a mano.',
    )

    @api.depends('categ_id')
    def _compute_target_markup_pct(self) -> None:
        for tmpl in self:
            tmpl.target_markup_pct = tmpl.categ_id.target_markup_pct
