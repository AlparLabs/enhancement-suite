from __future__ import annotations

from odoo import api, fields, models

from .res_partner import check_pct_range


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'commercial.conditions.access.mixin']

    _commercial_condition_fields = ('internal_tax_pct',)

    internal_tax_pct = fields.Float(
        string='Impuestos internos (%)',
        help='Valor por defecto para los productos de esta categoría.',
    )

    @api.constrains('internal_tax_pct')
    def _check_internal_tax_pct(self) -> None:
        check_pct_range(self, ('internal_tax_pct',), {'internal_tax_pct': 'Impuestos internos'})
