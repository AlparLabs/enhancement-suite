# -*- coding: utf-8 -*-
from odoo import _
from odoo.exceptions import UserError
from odoo.http import Controller, request, route
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale


class B2BOrderRulesCart(Cart):

    def _cart_values(self, **post):
        values = super()._cart_values(**post)
        website = request.website
        is_day_allowed = website.is_b2b_order_day_allowed() if website else True
        values['b2b_order_day_allowed'] = is_day_allowed
        values['b2b_allowed_days_display'] = website.b2b_allowed_days_display if website else ''
        values['b2b_min_amount_status'] = request.cart._get_b2b_min_amount_status() if request.cart else False
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
                "La toma de pedidos para el canal '%(channel)s' se encuentra cerrada en este momento. "
                "Horarios habilitados: %(days)s.",
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
        if request.cart and request.cart._get_b2b_min_amount_status().get('is_unmet'):
            return request.redirect('/shop/cart')
        return super().shop_checkout(try_skip_step=try_skip_step, **query_params)


class B2BQuickOrderPortal(Controller):

    @route(['/my/orders/<int:order_id>/reorder'], type='http', auth='user', website=True)
    def portal_order_reorder(self, order_id, **kw):
        """
        Clona los productos de un pedido anterior confirmado al carrito actual del cliente.
        """
        user = request.env.user
        order = request.env['sale.order'].browse(order_id)
        if not order.exists() or order.partner_id.commercial_partner_id != user.partner_id.commercial_partner_id:
            return request.redirect('/my/orders')

        website = request.website
        # 1. Verificar si el canal está abierto hoy por horario
        if not website.is_b2b_order_day_allowed():
            return request.redirect(f'/my/orders/{order_id}?error=schedule_closed')

        # 2. Verificar si el cliente tiene bloqueo financiero
        financial_status = user.partner_id.commercial_partner_id._get_b2b_financial_status(website)
        if financial_status.get('is_blocked'):
            return request.redirect(f'/my/orders/{order_id}?error=credit_blocked')

        # 3. Obtener o crear carrito activo de eCommerce
        cart = website.sale_get_order(force_create=True)
        for line in order.order_line:
            product = line.product_id
            if not product or not product.active or not product._is_add_to_cart_allowed():
                continue
            qty = line.product_uom_qty
            if qty > 0:
                try:
                    cart._cart_add(
                        product_id=product.id,
                        quantity=qty,
                        uom_id=line.product_uom.id if line.product_uom else product.uom_id.id,
                    )
                except Exception:
                    pass

        return request.redirect('/shop/cart')

    @route(['/shop/quick_order'], type='http', auth='user', website=True)
    def shop_quick_order(self, **kw):
        """
        Renderiza la matriz compacta de pedido rápido tipo planilla para el canal actual.
        """
        website = request.website
        user = request.env.user
        partner = user.partner_id.commercial_partner_id

        # Dominio de productos disponibles para este sitio web
        domain = [
            ('sale_ok', '=', True),
            ('active', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', website.id)
        ]
        products = request.env['product.template'].search(domain, order='sequence, name')
        pricelist = website.pricelist_id

        values = {
            'products': products,
            'pricelist': pricelist,
            'website': website,
            'user': user,
            'partner': partner,
            'is_day_allowed': website.is_b2b_order_day_allowed(),
            'financial_status': partner._get_b2b_financial_status(website),
        }
        return request.render('website_sale_b2b_order_rules.quick_order_page', values)

    @route(['/shop/quick_order/add'], type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def shop_quick_order_add(self, **post):
        """
        Procesa el formulario de pedido rápido agregando todas las cantidades al carrito.
        """
        website = request.website
        if not website.is_b2b_order_day_allowed():
            return request.redirect('/shop/quick_order?error=schedule_closed')

        financial_status = request.env.user.partner_id.commercial_partner_id._get_b2b_financial_status(website)
        if financial_status.get('is_blocked'):
            return request.redirect('/shop/quick_order?error=credit_blocked')

        cart = website.sale_get_order(force_create=True)
        for key, value in post.items():
            if key.startswith('qty_'):
                try:
                    product_id = int(key.replace('qty_', ''))
                    qty = float(value or 0.0)
                    if qty > 0:
                        product = request.env['product.product'].browse(product_id)
                        if product.exists() and product._is_add_to_cart_allowed():
                            cart._cart_add(product_id=product.id, quantity=qty)
                except Exception:
                    continue

        return request.redirect('/shop/cart')
