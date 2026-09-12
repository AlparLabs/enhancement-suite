# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        """
        Ajusta la cantidad al tope máximo permitido para el canal web si la cantidad deseada lo supera.
        """
        new_qty, warning = super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)
        website = self.website_id
        if website and product_id and new_qty > 0:
            product = self.env['product.product'].browse(product_id)
            rule = product._get_b2b_order_limit_for_website(website)
            if rule and rule.max_qty > 0 and new_qty > rule.max_qty:
                capped_qty = rule.max_qty
                uom = self.env['uom.uom'].browse(uom_id) if uom_id else product.uom_id
                warning = _(
                    "Para el canal '%(channel)s', la cantidad máxima permitida para '%(product)s' es de %(max_qty)s %(uom)s por pedido.",
                    channel=website.name,
                    product=product.display_name,
                    max_qty=int(capped_qty) if float(capped_qty).is_integer() else capped_qty,
                    uom=uom.name
                )
                return capped_qty, warning
        return new_qty, warning

    def _cart_add(self, product_id: int, quantity: float = 1.0, *, uom_id: int | None = None, **kwargs) -> dict:
        """
        Impide agregar productos al carrito si el día actual no está habilitado para pedidos en este canal web.
        """
        self.ensure_one()
        website = self.website_id
        if website and not website.is_b2b_order_day_allowed():
            raise UserError(_(
                "La toma de pedidos para el canal '%(channel)s' se encuentra cerrada hoy. "
                "Días habilitados: %(days)s.",
                channel=website.name,
                days=website.b2b_allowed_days_display
            ))
        return super()._cart_add(product_id=product_id, quantity=quantity, uom_id=uom_id, **kwargs)

    def _cart_update_line_quantity(self, line_id, quantity, **kwargs):
        """
        Impide modificar o reanudar cantidades en el carrito si el día actual no está habilitado.
        """
        self.ensure_one()
        website = self.website_id
        if website and not website.is_b2b_order_day_allowed():
            raise UserError(_(
                "La toma de pedidos para el canal '%(channel)s' se encuentra cerrada hoy. "
                "Días habilitados: %(days)s.",
                channel=website.name,
                days=website.b2b_allowed_days_display
            ))
        return super()._cart_update_line_quantity(line_id, quantity, **kwargs)

    def _get_b2b_min_amount_status(self):
        """
        Evalúa si la orden actual alcanza el monto mínimo configurado para el canal web.
        """
        self.ensure_one()
        website = self.website_id
        min_amount = website.b2b_min_order_amount if website else 0.0
        if min_amount > 0 and self.amount_total < min_amount:
            return {
                'is_unmet': True,
                'min_amount': min_amount,
                'current_amount': self.amount_total,
                'missing_amount': min_amount - self.amount_total,
            }
        return {
            'is_unmet': False,
            'min_amount': min_amount,
            'current_amount': self.amount_total,
            'missing_amount': 0.0,
        }

