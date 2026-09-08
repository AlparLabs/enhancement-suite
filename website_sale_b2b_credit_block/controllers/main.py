from odoo.http import request, route
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale


class B2BWebsiteSale(WebsiteSale):

    @route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
    ], type='http', auth='public', website=True, sitemap=False)
    def shop(self, **post):
        # Previene el bucle infinito de login para usuarios de portal sin acceso al canal actual
        if not request.website.has_ecommerce_access() and not request.env.user._is_public():
            return request.redirect('/my?channel_access_denied=1')
        return super().shop(**post)

    @route([
        '/shop/product/<model("product.template"):product>',
    ], type='http', auth='public', website=True, sitemap=False)
    def product(self, product, **kwargs):
        if not request.website.has_ecommerce_access() and not request.env.user._is_public():
            return request.redirect('/my?channel_access_denied=1')
        return super().product(product, **kwargs)

    def _prepare_checkout_page_values(self, order_sudo, **kwargs):
        values = super()._prepare_checkout_page_values(order_sudo, **kwargs)
        if order_sudo:
            values['b2b_financial_status'] = order_sudo._get_b2b_financial_status(request.website)
        return values

    @route('/shop/checkout', type='http', auth='public', website=True, sitemap=False)
    def checkout(self, **post):
        if not request.website.has_ecommerce_access():
            if not request.env.user._is_public():
                return request.redirect('/my?channel_access_denied=1')
            return request.redirect('/web/login?redirect=/shop/checkout')

        order_sudo = request.cart
        if order_sudo:
            status = order_sudo._get_b2b_financial_status(request.website)
            if status.get('is_blocked'):
                # Redirige al carrito para mostrar el aviso de bloqueo financiero
                return request.redirect('/shop/cart')

        return super().checkout(**post)


class B2BCart(Cart):

    @route(['/shop/cart'], type='http', auth='public', website=True, sitemap=False)
    def cart(self, **post):
        if not request.website.has_ecommerce_access() and not request.env.user._is_public():
            return request.redirect('/my?channel_access_denied=1')

        response = super().cart(**post)
        if hasattr(response, 'qcontext') and request.cart:
            response.qcontext['b2b_financial_status'] = request.cart._get_b2b_financial_status(request.website)
        return response
