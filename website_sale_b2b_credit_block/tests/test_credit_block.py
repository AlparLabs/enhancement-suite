from datetime import timedelta
from odoo import fields
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestB2BCreditBlock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Websites de prueba
        cls.website_franquicias = cls.env['website'].create({
            'name': 'EntreDos Franquicias',
            'b2b_credit_block_active': True,
            'b2b_grace_period_days': 5,
        })
        cls.website_distribucion = cls.env['website'].create({
            'name': 'EntreDos Distribución',
            'b2b_credit_block_active': True,
            'b2b_grace_period_days': 0,
        })

        # Partner Padre (Comercial)
        cls.partner_parent = cls.env['res.partner'].create({
            'name': 'Empresa Franquiciada SA',
            'is_company': True,
            'credit_limit': 1000000.0,  # $1M
        })

        # Partner Hijo (Canal Franquicia)
        cls.partner_child_franq = cls.env['res.partner'].create({
            'name': 'Franquicia Centro',
            'parent_id': cls.partner_parent.id,
            'b2b_website_ids': [(6, 0, [cls.website_franquicias.id])],
        })

        # Producto para órdenes
        cls.product = cls.env['product.product'].create({
            'name': 'Alfajor Chocolate EntreDos',
            'list_price': 1000.0,
            'type': 'consu',
        })

    def test_01_no_debt_no_block(self):
        """Un cliente sin deuda ni facturas vencidas puede comprar normalmente."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner_child_franq.id,
            'website_id': self.website_franquicias.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 100,  # $100.000
                    'price_unit': 1000.0,
                })
            ],
        })

        status = order._get_b2b_financial_status(self.website_franquicias)
        self.assertFalse(status['is_blocked'])
        self.assertFalse(status['has_overdue'])
        self.assertFalse(status['exceeds_limit'])
        self.assertEqual(status['excess_amount'], 0.0)

    def test_02_overdue_invoice_within_grace_period(self):
        """Factura vencida hace 3 días, con 5 días de gracia no debe bloquear."""
        today = fields.Date.context_today(self.partner_parent)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_child_franq.id,
            'invoice_date': today - timedelta(days=10),
            'invoice_date_due': today - timedelta(days=3),  # Venció hace 3 días
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 10,
                    'price_unit': 1000.0,
                })
            ],
        })
        invoice.action_post()

        order = self.env['sale.order'].create({
            'partner_id': self.partner_child_franq.id,
            'website_id': self.website_franquicias.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 10,
                    'price_unit': 1000.0,
                })
            ],
        })

        # En Franquicias (5 días de gracia): NO bloquea
        status_franq = order._get_b2b_financial_status(self.website_franquicias)
        self.assertFalse(status_franq['is_blocked'])
        self.assertFalse(status_franq['has_overdue'])

        # En Distribución (0 días de gracia): BLOQUEA
        status_dist = order._get_b2b_financial_status(self.website_distribucion)
        self.assertTrue(status_dist['is_blocked'])
        self.assertTrue(status_dist['has_overdue'])

    def test_03_overdue_invoice_past_grace_period(self):
        """Factura vencida hace 7 días, con 5 días de gracia debe bloquear."""
        today = fields.Date.context_today(self.partner_parent)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_child_franq.id,
            'invoice_date': today - timedelta(days=15),
            'invoice_date_due': today - timedelta(days=7),  # Venció hace 7 días
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 50,
                    'price_unit': 1000.0,
                })
            ],
        })
        invoice.action_post()

        order = self.env['sale.order'].create({
            'partner_id': self.partner_child_franq.id,
            'website_id': self.website_franquicias.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 10,
                    'price_unit': 1000.0,
                })
            ],
        })

        status = order._get_b2b_financial_status(self.website_franquicias)
        self.assertTrue(status['is_blocked'])
        self.assertTrue(status['has_overdue'])

        # Pero si el partner tiene un override personalizado de 10 días de gracia, no bloquea
        self.partner_parent.b2b_grace_period_override = 10
        status_override = order._get_b2b_financial_status(self.website_franquicias)
        self.assertFalse(status_override['is_blocked'])

    def test_04_credit_limit_calculation_invoiced_only(self):
        """
        Límite: $1.000.000
        Deuda facturada: $800.000
        Nuevo pedido: $300.000
        Total exposición: $1.100.000 -> Exceso: $100.000
        """
        today = fields.Date.context_today(self.partner_parent)
        # Crear factura no vencida por $800.000
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_parent.id,
            'invoice_date': today,
            'invoice_date_due': today + timedelta(days=30),  # No vencida
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 800,
                    'price_unit': 1000.0,
                })
            ],
        })
        invoice.action_post()

        # Verificar que la deuda contable del partner es 800k
        self.assertEqual(self.partner_parent.credit, 800000.0)

        # Pedido por 300k
        order = self.env['sale.order'].create({
            'partner_id': self.partner_child_franq.id,
            'website_id': self.website_franquicias.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 300,
                    'price_unit': 1000.0,
                })
            ],
        })

        status = order._get_b2b_financial_status(self.website_franquicias)
        self.assertTrue(status['is_blocked'])
        self.assertFalse(status['has_overdue'])
        self.assertTrue(status['exceeds_limit'])
        self.assertEqual(status['invoiced_debt'], 800000.0)
        self.assertEqual(status['excess_amount'], 100000.0)

    def test_06_cart_add_prevented_when_blocked(self):
        """Verifica que no se permita agregar productos al carrito si el cliente tiene bloqueo financiero."""
        today = fields.Date.context_today(self.partner_parent)
        # Crear factura vencida fuera de días de gracia
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_child_franq.id,
            'invoice_date': today - timedelta(days=20),
            'invoice_date_due': today - timedelta(days=10),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'quantity': 10,
                    'price_unit': 1000.0,
                })
            ],
        })
        invoice.action_post()

        order = self.env['sale.order'].create({
            'partner_id': self.partner_child_franq.id,
            'website_id': self.website_franquicias.id,
        })

        # Al intentar agregar al carrito, debe levantar UserError por deuda vencida
        with self.assertRaises(UserError):
            order._cart_add(self.product.id, 1.0)

