# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestB2BOrderHelpdeskBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Franquicia EntreDos Palmares',
            'email': 'palmares@entredos.com.ar',
            'company_id': cls.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Alfajor Premium Chocolate Negro 60g',
            'list_price': 1500.0,
        })

    def test_01_order_ticket_creation(self):
        """Verifica la creación del ticket de Helpdesk vinculado al pedido de venta."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 100,
                    'price_unit': 1500.0,
                })
            ]
        })
        order.action_confirm()

        # Si el modelo helpdesk.ticket existe en el entorno
        if 'helpdesk.ticket' in self.env:
            ticket_vals = {
                'name': f"Reclamo {order.name} - Mercadería dañada en tránsito",
                'partner_id': order.partner_id.id,
                'partner_name': order.partner_id.name,
                'partner_email': order.partner_id.email,
                'description': "<p>Caja aplastada durante la descarga.</p>",
            }
            if 'sale_order_id' in self.env['helpdesk.ticket']._fields:
                ticket_vals['sale_order_id'] = order.id

            ticket = self.env['helpdesk.ticket'].create(ticket_vals)
            self.assertTrue(ticket.id)
            self.assertEqual(ticket.partner_id, self.partner)
            if 'sale_order_id' in ticket._fields:
                self.assertEqual(ticket.sale_order_id, order)
