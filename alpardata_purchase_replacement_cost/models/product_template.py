from __future__ import annotations

from odoo import api, fields, models

from ..tools import compute_replacement_cost
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

    replacement_cost = fields.Float(
        string='Costo de reposición',
        digits='Product Price',
        compute='_compute_replacement_cost',
        help='Costo de referencia del proveedor vigente aplicando bonificaciones en '
             'cascada, pronto pago, flete, percepción e impuestos internos.',
    )
    net_purchase_cost = fields.Float(
        string='Neto bonificado',
        digits='Product Price',
        compute='_compute_replacement_cost',
        help='Costo de referencia menos bonificaciones en cascada (sin adicionales).',
    )

    @api.depends('categ_id')
    def _compute_internal_tax_pct(self) -> None:
        for tmpl in self:
            tmpl.internal_tax_pct = tmpl.categ_id.internal_tax_pct

    @api.constrains('internal_tax_pct')
    def _check_internal_tax_pct(self) -> None:
        check_pct_range(self, ('internal_tax_pct',), {'internal_tax_pct': 'Impuestos internos'})

    @api.depends(
        'reference_cost', 'internal_tax_pct',
        'seller_ids.discount_equivalent_pct',
        'seller_ids.effective_early_payment_pct',
        'seller_ids.effective_freight_pct',
        'seller_ids.effective_perception_pct',
    )
    @api.depends_context('company')
    def _compute_replacement_cost(self) -> None:
        """Aplica la fórmula sobre `reference_cost`, que ya viene convertido a la
        UoM del producto y a la moneda de la empresa, usando las condiciones del
        mismo proveedor que eligió el resolver de `reference_cost`."""
        for tmpl in self:
            seller = tmpl._get_reference_cost_seller()
            if not seller or not tmpl.reference_cost:
                tmpl.replacement_cost = 0.0
                tmpl.net_purchase_cost = 0.0
                continue
            net, replacement = compute_replacement_cost(
                tmpl.reference_cost,
                seller.discount_equivalent_pct,
                seller.effective_early_payment_pct,
                seller.effective_freight_pct,
                seller.effective_perception_pct,
                tmpl.internal_tax_pct,
            )
            tmpl.net_purchase_cost = net
            tmpl.replacement_cost = replacement

    def _get_divergence_base_cost(self) -> float:
        """El AVCO sale de facturas ya bonificadas: se compara contra el neto
        bonificado, no contra la lista."""
        self.ensure_one()
        return self.net_purchase_cost or super()._get_divergence_base_cost()

    @api.depends('standard_price', 'reference_cost', 'net_purchase_cost')
    def _compute_cost_divergence(self) -> None:
        return super()._compute_cost_divergence()

