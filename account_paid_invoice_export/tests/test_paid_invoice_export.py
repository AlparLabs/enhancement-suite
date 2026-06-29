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
