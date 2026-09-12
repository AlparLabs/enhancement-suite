# -*- coding: utf-8 -*-
import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        """
        Ajusta la cantidad al múltiplo de empaque y al tope máximo permitido para el canal web.
        """
        new_qty, warning = super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)
        website = self.website_id
        if website and product_id and new_qty > 0:
            product = self.env['product.product'].browse(product_id)
            uom = self.env['uom.uom'].browse(uom_id) if uom_id else product.uom_id

            # 1. Regulación por Múltiplos de Empaque / Bulto Cerrado
            pkg_qty, pkg_name = product._get_b2b_packaging_info(website)
            if pkg_qty > 1.0:
                remainder = new_qty % pkg_qty
                # Tolerancia flotante
                if remainder > 1e-4 and abs(remainder - pkg_qty) > 1e-4:
                    adjusted_qty = math.ceil(round(new_qty, 4) / pkg_qty) * pkg_qty
                    display_pkg = int(pkg_qty) if float(pkg_qty).is_integer() else pkg_qty
                    display_adj = int(adjusted_qty) if float(adjusted_qty).is_integer() else adjusted_qty
                    warning = _(
                        "Para el canal '%(channel)s', el producto '%(product)s' se comercializa en %(pkg_name)s "
                        "(múltiplos de %(pkg)s %(uom)s). La cantidad fue ajustada a %(adj)s %(uom)s.",
                        channel=website.name,
                        product=product.display_name,
                        pkg_name=pkg_name,
                        pkg=display_pkg,
                        adj=display_adj,
                        uom=uom.name
                    )
                    new_qty = adjusted_qty

            # 2. Regulación por Tope Máximo por Pedido
            rule = product._get_b2b_order_limit_for_website(website)
            if rule and rule.max_qty > 0 and new_qty > rule.max_qty:
                capped_qty = rule.max_qty
                if pkg_qty > 1.0 and (capped_qty % pkg_qty) > 1e-4:
                    capped_qty = math.floor(round(capped_qty, 4) / pkg_qty) * pkg_qty
                display_max = int(capped_qty) if float(capped_qty).is_integer() else capped_qty
                warning = _(
                    "Para el canal '%(channel)s', la cantidad máxima permitida para '%(product)s' es de %(max_qty)s %(uom)s por pedido.",
                    channel=website.name,
                    product=product.display_name,
                    max_qty=display_max,
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
