# -*- coding: utf-8 -*-
from odoo import _
from odoo.http import request, route
from odoo.addons.website_sale.controllers.main import WebsiteSale


class B2BDeliveryScheduleWebsiteSale(WebsiteSale):

    def _prepare_checkout_page_values(self, order_sudo, **kwargs):
        """
        Inyecta la información de programación de entrega y calcula la fecha más próxima en el checkout.
        """
        values = super()._prepare_checkout_page_values(order_sudo, **kwargs)
        website = request.website
        if website and website.b2b_delivery_schedule_active and order_sudo:
            earliest_date = website._get_b2b_earliest_delivery_date()
            if not order_sudo.b2b_requested_delivery_date:
                try:
                    order_sudo.set_b2b_delivery_schedule(earliest_date, 'morning')
                except Exception:
                    pass
            values['b2b_earliest_delivery_date'] = earliest_date.strftime('%Y-%m-%d')
            values['b2b_delivery_schedule_active'] = True
        return values

    @route('/shop/b2b/set_delivery_schedule', type='jsonrpc', auth='public', website=True)
    def shop_set_b2b_delivery_schedule(self, delivery_date, delivery_shift='morning', delivery_notes=None):
        """
        Persiste la fecha, turno y notas de entrega en tiempo real desde el formulario de checkout.
        """
        order_sudo = request.cart
        if not order_sudo:
            return {'success': False, 'error': _("No hay pedido activo en el carrito.")}
        try:
            order_sudo.set_b2b_delivery_schedule(delivery_date, delivery_shift, delivery_notes)
            return {
                'success': True,
                'requested_date': str(order_sudo.b2b_requested_delivery_date),
                'shift': order_sudo.b2b_delivery_shift,
                'commitment_date': str(order_sudo.commitment_date) if order_sudo.commitment_date else False,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
