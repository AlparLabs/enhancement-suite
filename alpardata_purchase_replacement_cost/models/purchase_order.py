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
