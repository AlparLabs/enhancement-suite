from __future__ import annotations

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    _commercial_condition_fields = ('internal_tax_pct', 'target_markup_pct')

    target_markup_pct = fields.Float(
        string='Recargo objetivo (%)',
        help='Recargo esperado sobre el costo de reposición (precio sin impuestos / reposición − 1).',
    )
