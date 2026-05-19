from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestSaleProgressCertification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
            'invoice_policy': 'order',
            'list_price': 1000.0,
        })
        cls.tax = cls.env['account.tax'].create({
            'name': 'Tax 21%',
            'amount': 21.0,
            'type_tax_use': 'sale',
        })
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 1000.0,
                'tax_id': [(6, 0, [cls.tax.id])],
            })],
        })
        cls.sale_order.action_confirm()

    def _make_wizard(self, method, amount=None, fixed_amount=None):
        vals = {
            'advance_payment_method': method,
            'sale_order_ids': [(6, 0, [self.sale_order.id])],
        }
        if amount is not None:
            vals['amount'] = amount
        if fixed_amount is not None:
            vals['fixed_amount'] = fixed_amount
        return self.env['sale.advance.payment.inv'].with_context(
            active_ids=[self.sale_order.id],
            active_model='sale.order',
        ).create(vals)

    def test_percentage_progress_creates_invoice_with_custom_description(self):
        wizard = self._make_wizard('percentage_progress', amount=30)
        wizard.create_invoices()

        invoices = self.sale_order.invoice_ids
        self.assertEqual(len(invoices), 1)

        dp_lines = invoices.invoice_line_ids.filtered('is_downpayment')
        self.assertTrue(dp_lines, "Debe existir al menos una línea de anticipo")
        self.assertIn('Certificación de Avance: 30%', dp_lines[0].name)

    def test_percentage_progress_restores_method_on_success(self):
        wizard = self._make_wizard('percentage_progress', amount=20)
        wizard.create_invoices()
        self.assertEqual(wizard.advance_payment_method, 'percentage_progress')

    def test_percentage_progress_restores_method_on_error(self):
        wizard = self._make_wizard('percentage_progress', amount=20)
        original_super = type(wizard).create_invoices

        def failing_super(self_inner):
            raise ValueError("Simulated failure")

        type(wizard).create_invoices = failing_super
        try:
            with self.assertRaises(ValueError):
                original_super(wizard)
        finally:
            type(wizard).create_invoices = original_super

        self.assertEqual(wizard.advance_payment_method, 'percentage_progress')

    def test_fixed_net_creates_invoice_with_net_price_unit(self):
        net_amount = 500.0
        wizard = self._make_wizard('fixed_net', fixed_amount=net_amount)
        wizard.create_invoices()

        invoices = self.sale_order.invoice_ids
        self.assertEqual(len(invoices), 1)

        dp_lines = invoices.invoice_line_ids.filtered('is_downpayment')
        self.assertTrue(dp_lines, "Debe existir al menos una línea de anticipo")
        self.assertAlmostEqual(dp_lines[0].price_unit, net_amount, places=2)
        self.assertIn('Monto Fijo Neto', dp_lines[0].name)

    def test_fixed_net_restores_method_after_creation(self):
        wizard = self._make_wizard('fixed_net', fixed_amount=200.0)
        wizard.create_invoices()
        self.assertEqual(wizard.advance_payment_method, 'fixed_net')

    def test_standard_method_delegates_to_super(self):
        wizard = self._make_wizard('delivered')
        result = wizard.create_invoices()
        self.assertIsNotNone(result)
