from __future__ import annotations

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_replacement_cost_for(self, company, uom, currency, date) -> tuple[float, bool]:
        """Costo de reposición unitario en `uom` y `currency`.

        Devuelve (costo, is_fallback). Si el producto no tiene costo de
        reposición usa `standard_price` (mismo criterio que las listas de
        precios) e informa is_fallback=True.
        """
        self.ensure_one()
        product = self.with_company(company)
        cost = product.replacement_cost
        is_fallback = not cost
        if is_fallback:
            cost = product.standard_price
        if uom and product.uom_id and uom != product.uom_id:
            cost = product.uom_id._compute_price(cost, uom)
        if currency and currency != company.currency_id:
            cost = company.currency_id._convert(cost, currency, company, date, round=False)
        return cost, is_fallback
