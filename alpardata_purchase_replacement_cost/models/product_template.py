from __future__ import annotations

from odoo import api, fields, models

from .res_partner import check_pct_range


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'commercial.conditions.access.mixin']

    _commercial_condition_fields = ('internal_tax_pct',)

    internal_tax_pct = fields.Float(
        string='Impuestos internos (%)',
        compute='_compute_internal_tax_pct',
        store=True,
        readonly=False,
        precompute=True,
        help='Se toma de la categoría al crear el producto o al cambiarlo de '
             'categoría. Se puede modificar a mano.',
    )

    @api.depends('categ_id')
    def _compute_internal_tax_pct(self) -> None:
        for tmpl in self:
            tmpl.internal_tax_pct = tmpl.categ_id.internal_tax_pct

    @api.constrains('internal_tax_pct')
    def _check_internal_tax_pct(self) -> None:
        check_pct_range(self, ('internal_tax_pct',), {'internal_tax_pct': 'Impuestos internos'})
