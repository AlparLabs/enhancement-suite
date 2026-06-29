from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPaidInvoiceExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard = cls.env['paid.invoice.export.wizard'].create({})

    def test_domain_includes_selected_states_only(self):
        self.wizard.incl_paid = True
        self.wizard.incl_partial = False
        self.wizard.incl_in_payment = False
        domain = self.wizard._get_invoice_domain()
        self.assertIn(('move_type', '=', 'out_invoice'), domain)
        self.assertIn(('state', '=', 'posted'), domain)
        self.assertIn(('payment_state', 'in', ['paid']), domain)

    def test_no_states_selected_raises(self):
        from odoo.exceptions import UserError
        self.wizard.incl_paid = False
        self.wizard.incl_partial = False
        self.wizard.incl_in_payment = False
        with self.assertRaises(UserError):
            self.wizard.action_export()

    def test_paid_invoice_expands_to_payment_row(self):
        partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        product = self.env['product.product'].create({
            'name': 'Producto Test',
            'lst_price': 100.0,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': '2026-01-15',
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()

        # Register a full payment via the standard payment register wizard.
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({}).action_create_payments()

        self.assertEqual(invoice.payment_state, 'paid')

        self.wizard.incl_paid = True
        self.wizard.incl_partial = True
        self.wizard.incl_in_payment = True
        rows = self.wizard._build_rows()

        invoice_rows = [r for r in rows if r[0] == invoice.name]
        self.assertTrue(invoice_rows, 'invoice should appear in export rows')
        row = invoice_rows[0]
        self.assertEqual(row[1], 'Cliente Test')          # Cliente
        self.assertEqual(row[7], 'paid')                  # Estado de Pago
        self.assertIsNotNone(row[9])                      # Fecha de Pago set
        self.assertEqual(row[13], 'No')                   # Es Nota de Crédito
        self.assertAlmostEqual(row[12], 100.0, places=2)  # Monto Aplicado (ARS)
