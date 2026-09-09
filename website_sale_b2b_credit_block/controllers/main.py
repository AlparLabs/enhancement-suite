import logging
from odoo.http import content_disposition, request, route
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class B2BWebsiteSale(WebsiteSale):

    @route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
    ], type='http', auth='public', website=True, sitemap=False)
    def shop(self, *args, **post):
        # Previene el bucle infinito de login para usuarios de portal sin acceso al canal actual
        if not request.website.has_ecommerce_access() and not request.env.user._is_public():
            return request.redirect('/my?channel_access_denied=1')
        return super().shop(*args, **post)

    @route([
        '/shop/<model("product.template"):product>',
        '/shop/<model("product.public.category"):category>/<model("product.template"):product>',
        '/shop/product/<model("product.template"):product>',
    ], type='http', auth='public', website=True, sitemap=False)
    def product(self, product, category=None, pricelist=None, **kwargs):
        if not request.website.has_ecommerce_access() and not request.env.user._is_public():
            return request.redirect('/my?channel_access_denied=1')
        return super().product(product, category=category, pricelist=pricelist, **kwargs)

    def _prepare_checkout_page_values(self, order_sudo, **kwargs):
        values = super()._prepare_checkout_page_values(order_sudo, **kwargs)
        if order_sudo:
            values['b2b_financial_status'] = order_sudo._get_b2b_financial_status(request.website)
        return values

    @route(
        '/shop/checkout',
        type='http',
        methods=['GET'],
        auth='public',
        website=True,
        sitemap=False,
    )
    def shop_checkout(self, try_skip_step=None, **query_params):
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

        return super().shop_checkout(try_skip_step=try_skip_step, **query_params)


class B2BCart(Cart):

    @route(route='/shop/cart', type='http', auth='public', website=True, sitemap=False)
    def cart(self, *args, **post):
        if not request.website.has_ecommerce_access() and not request.env.user._is_public():
            return request.redirect('/my?channel_access_denied=1')
        return super().cart(*args, **post)

    def _cart_values(self, **post):
        values = super()._cart_values(**post)
        if request.cart:
            values['b2b_financial_status'] = request.cart._get_b2b_financial_status(request.website)
        return values


class B2BCustomerPortal(CustomerPortal):

    @route(['/my/account_statement/pdf'], type='http', auth='user', website=True)
    def download_statement_pdf(self, **kwargs):
        """
        Descarga el estado de cuenta oficial (Follow-up Report) de Odoo Enterprise
        para el contacto logueado (commercial_partner_id).
        """
        partner = request.env.user.partner_id.commercial_partner_id
        if not partner:
            return request.redirect('/my')

        # 1. Método oficial de account_followup (Odoo Enterprise)
        if hasattr(partner, '_get_followup_report_pdf'):
            try:
                filename, pdf_content = partner.sudo()._get_followup_report_pdf(options={})
                return request.make_response(
                    pdf_content,
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Length', len(pdf_content)),
                        ('Content-Disposition', content_disposition(filename)),
                    ]
                )
            except Exception as e:
                _logger.warning("Error generando informe de seguimiento para partner %s: %s", partner.id, e)

        # 2. Fallback: reporte directo account_followup.action_report_followup
        report = request.env.ref('account_followup.action_report_followup', raise_if_not_found=False)
        if report:
            try:
                pdf_content, _ = report.sudo()._render_qweb_pdf(
                    'account_followup.report_followup_print_all',
                    [partner.id],
                    data={'options': {}}
                )
                filename = f"Estado_de_Cuenta_{partner.name}.pdf"
                return request.make_response(
                    pdf_content,
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Length', len(pdf_content)),
                        ('Content-Disposition', content_disposition(filename)),
                    ]
                )
            except Exception as e:
                _logger.warning("Error renderizando action_report_followup para partner %s: %s", partner.id, e)

        return request.redirect('/my/invoices')
