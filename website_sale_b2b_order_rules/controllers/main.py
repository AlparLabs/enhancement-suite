# -*- coding: utf-8 -*-
from odoo import _
from odoo.exceptions import UserError
from odoo.http import request, route
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale


class B2BOrderRulesCart(Cart):

    def _cart_values(self, **post):
        values = super()._cart_values(**post)
        website = request.website
        is_day_allowed = website.is_b2b_order_day_allowed() if website else True
        values['b2b_order_day_allowed'] = is_day_allowed
        values['b2b_allowed_days_display'] = website.b2b_allowed_days_display if website else ''
        return values

    def add_to_cart(
        self,
        product_template_id,
        product_id,
        quantity=1.0,
        uom_id=None,
        product_custom_attribute_values=None,
        no_variant_attribute_value_ids=None,
        linked_products=None,
        **kwargs
    ):
        website = request.website
        if website and not website.is_b2b_order_day_allowed():
            raise UserError(_(
                "La toma de pedidos para el canal '%(channel)s' se encuentra cerrada hoy. "
                "Días habilitados: %(days)s.",
                channel=website.name,
                days=website.b2b_allowed_days_display
            ))
        return super().add_to_cart(
            product_template_id,
            product_id,
            quantity=quantity,
            uom_id=uom_id,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            linked_products=linked_products,
            **kwargs
        )


class B2BOrderRulesWebsiteSale(WebsiteSale):

    def shop_checkout(self, try_skip_step=None, **query_params):
        website = request.website
        if website and not website.is_b2b_order_day_allowed():
            return request.redirect('/shop/cart')
        return super().shop_checkout(try_skip_step=try_skip_step, **query_params)
