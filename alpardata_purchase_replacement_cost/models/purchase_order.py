from __future__ import annotations

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _update_order_line_info(self, product_id, quantity, *, section_id=False, **kwargs):
        """Alta desde el catálogo: aplica la cascada después de que el módulo
        base fija el precio de referencia. Busca la línea igual que el base
        (producto + sección)."""
        price = super()._update_order_line_info(
            product_id, quantity, section_id=section_id, **kwargs
        )
        line = self.order_line.filtered(
            lambda pol: pol.product_id.id == product_id
            and pol.get_parent_section_line().id == section_id
        )[:1]
        if line:
            line._apply_discount_cascade()
            return line.price_unit_discounted
        return price

    def _get_product_price_and_data(self, product):
        """Tarjeta del catálogo: el base muestra la lista (reference_cost); acá
        se le aplica la cascada para que coincida con lo que devuelve
        `_update_order_line_info` al agregar el producto."""
        product_infos = super()._get_product_price_and_data(product)
        seller = self.env['purchase.order.line']._get_cascade_seller(
            product, self.company_id or self.env.company, self.partner_id,
        )
        if seller and seller.effective_discount_cascade and self._get_reference_cost_price(
            product, uom=product.uom_id,
        ) > 0:
            product_infos['price'] *= 1 - seller.discount_equivalent_pct / 100
        return product_infos
