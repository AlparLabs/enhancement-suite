from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo import fields


@tagged('post_install', '-at_install')
class TestCashClosureReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report_model = cls.env['report.sale_vendor_cash_closure.cash_closure_vendor']
        cls.today = fields.Date.today()

        cls.product = cls.env['product.product'].create({
            'name': 'Producto Test',
            'type': 'service',
            'lst_price': 100.0,
        })

        cls.partner_contado = cls.env['res.partner'].create({
            'name': 'Cliente Contado',
            'use_partner_credit_limit': False,
        })
        cls.partner_ctacte = cls.env['res.partner'].create({
            'name': 'Cliente Cuenta Corriente',
            'use_partner_credit_limit': True,
        })

        # Generic LATAM document types (from l10n_latam_invoice_document),
        # not tied to a specific AFIP posting flow — enough to exercise
        # the classification logic without needing full AR CAE setup.
        country_ar = cls.env.ref('base.ar')
        cls.doc_type_normal = cls.env['l10n_latam.document.type'].create({
            'name': 'Factura Test',
            'code': '999',
            'country_id': country_ar.id,
            'doc_code_prefix': 'FA-',
        })
        cls.doc_type_fce_invoice = cls.env['l10n_latam.document.type'].create({
            'name': 'FCE Factura MiPyme A Test',
            'code': '201',
            'country_id': country_ar.id,
            'doc_code_prefix': 'FCE-',
        })
        cls.doc_type_fce_credit = cls.env['l10n_latam.document.type'].create({
            'name': 'FCE Nota de Crédito MiPyme A Test',
            'code': '203',
            'country_id': country_ar.id,
            'doc_code_prefix': 'NCF-',
        })

    def _create_move(self, partner, move_type='out_invoice', doc_type=None, price_unit=100.0, discount=0.0):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': self.today,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': price_unit,
                'discount': discount,
            })],
        })
        if doc_type:
            move.l10n_latam_document_type_id = doc_type.id
        return move

    # -- Task 2: classification --------------------------------------------

    def test_classify_contado_invoice(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal)
        self.assertEqual(self.report_model._classify_move(move), 'contado')

    def test_classify_ctacte_invoice(self):
        move = self._create_move(self.partner_ctacte, doc_type=self.doc_type_normal)
        self.assertEqual(self.report_model._classify_move(move), 'cta_cte_nd')

    def test_classify_contado_refund(self):
        move = self._create_move(self.partner_contado, move_type='out_refund', doc_type=self.doc_type_normal)
        self.assertEqual(self.report_model._classify_move(move), 'nc_contado')

    def test_classify_ctacte_refund(self):
        move = self._create_move(self.partner_ctacte, move_type='out_refund', doc_type=self.doc_type_normal)
        self.assertEqual(self.report_model._classify_move(move), 'nc_dev_ctacte_dia')

    def test_classify_fce_invoice_overrides_partner(self):
        # Partner is CtaCte, but the FCE document type takes priority.
        move = self._create_move(self.partner_ctacte, doc_type=self.doc_type_fce_invoice)
        self.assertEqual(self.report_model._classify_move(move), 'fact_mipyme')

    def test_classify_fce_credit_note(self):
        move = self._create_move(self.partner_contado, move_type='out_refund', doc_type=self.doc_type_fce_credit)
        self.assertEqual(self.report_model._classify_move(move), 'nc_mipyme')

    # -- Task 3: discounts --------------------------------------------------

    def test_compute_discount_no_discount(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0, discount=0.0)
        pct, amount = self.report_model._compute_discount(move)
        self.assertEqual(pct, 0.0)
        self.assertEqual(amount, 0.0)

    def test_compute_discount_with_discount(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0, discount=10.0)
        pct, amount = self.report_model._compute_discount(move)
        self.assertAlmostEqual(pct, 10.0, places=2)
        # 10% of 100 pre-tax = 10.0 discount, scaled by move's tax factor
        expected_amount = 10.0 * (move.amount_total / move.amount_untaxed)
        self.assertAlmostEqual(amount, expected_amount, places=2)

    # -- Task 4: vendor resolution -----------------------------------------

    def test_resolve_move_vendor_falls_back_to_invoice_user(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal)
        move.invoice_user_id = self.env.user
        pos_order = self.env['pos.order']  # empty recordset: no linked POS order
        vendor_key, vendor_name = self.report_model._resolve_move_vendor(move, pos_order)
        self.assertEqual(vendor_key, ('res.users', self.env.user.id))
        self.assertEqual(vendor_name, self.env.user.name)

    def test_resolve_move_vendor_unassigned(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal)
        move.invoice_user_id = False
        pos_order = self.env['pos.order']
        vendor_key, vendor_name = self.report_model._resolve_move_vendor(move, pos_order)
        self.assertEqual(vendor_key, (False, False))
        self.assertEqual(vendor_name, 'Sin vendedor')

    def test_resolve_payment_vendor_from_partner_salesperson(self):
        self.partner_contado.user_id = self.env.user
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_contado.id,
            'amount': 500.0,
            'date': self.today,
        })
        vendor_key, vendor_name = self.report_model._resolve_payment_vendor(payment)
        self.assertEqual(vendor_key, ('res.users', self.env.user.id))
        self.assertEqual(vendor_name, self.env.user.name)

    # -- Task 5: pricelist resolution --------------------------------------

    def test_resolve_pricelist_from_sale_order(self):
        pricelist = self.env['product.pricelist'].create({'name': 'Lista Test'})
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_contado.id,
            'pricelist_id': pricelist.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        sale_order.action_confirm()
        invoice_id = sale_order._create_invoices()
        pos_order = self.env['pos.order']
        result = self.report_model._resolve_pricelist(invoice_id, pos_order)
        self.assertEqual(result, 'Lista Test')

    def test_resolve_pricelist_empty_when_no_origin(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal)
        pos_order = self.env['pos.order']
        result = self.report_model._resolve_pricelist(move, pos_order)
        self.assertEqual(result, '')

    # -- Task 6: row builders ----------------------------------------------

    def test_build_move_row_contado(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0)
        vendor_key, vendor_name, row = self.report_model._build_move_row(move)
        self.assertEqual(vendor_key, (False, False))
        self.assertEqual(vendor_name, 'Sin vendedor')
        self.assertEqual(row['number'], move.name)
        self.assertEqual(row['partner_name'], self.partner_contado.name)
        self.assertEqual(row['contado'], move.amount_total)
        self.assertEqual(row['cta_cte_nd'], 0.0)
        self.assertEqual(row['cantidad_cc'], 0.0)

    def test_build_move_row_ctacte_sets_cantidad_cc(self):
        move = self._create_move(self.partner_ctacte, doc_type=self.doc_type_normal, price_unit=100.0)
        _key, _name, row = self.report_model._build_move_row(move)
        self.assertEqual(row['cta_cte_nd'], move.amount_total)
        self.assertEqual(row['cantidad_cc'], 1.0)

    def test_build_move_row_same_currency_amount_unchanged(self):
        # The common case (invoice currency == company currency): no FX
        # conversion should be applied, amount passes through as-is.
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0)
        self.assertEqual(move.currency_id, move.company_currency_id)
        _key, _name, row = self.report_model._build_move_row(move)
        self.assertEqual(row['contado'], move.amount_total)

    def test_build_payment_row(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_ctacte.id,
            'amount': 750.0,
            'date': self.today,
        })
        vendor_key, vendor_name, row = self.report_model._build_payment_row(payment)
        self.assertEqual(vendor_key, (False, False))
        self.assertEqual(vendor_name, 'Sin vendedor')
        self.assertEqual(row['dev_ctacte_dia_ant'], 750.0)
        self.assertEqual(row['contado'], 0.0)
        self.assertEqual(row['lista'], '')

    # -- Task 7: aggregation -----------------------------------------------

    def test_compute_data_groups_and_totals(self):
        self.env.user.name = 'Vendedor Uno'
        move1 = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0)
        move1.invoice_user_id = self.env.user
        move1.action_post()

        move2 = self._create_move(self.partner_ctacte, doc_type=self.doc_type_normal, price_unit=200.0)
        move2.invoice_user_id = False  # falls into "Sin vendedor"
        move2.action_post()

        self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_ctacte.id,
            'amount': 50.0,
            'date': self.today,
        }).action_post()

        data = self.report_model._compute_data(self.today, self.env.company)

        self.assertEqual(data['date'], self.today)
        group_names = [g['salesperson_name'] for g in data['groups']]
        self.assertIn('Vendedor Uno', group_names)
        self.assertIn('Sin vendedor', group_names)
        # "Sin vendedor" must be sorted last
        self.assertEqual(group_names[-1], 'Sin vendedor')

        vendor_group = next(g for g in data['groups'] if g['salesperson_name'] == 'Vendedor Uno')
        self.assertEqual(vendor_group['subtotal']['contado'], move1.amount_total)

        unassigned_group = next(g for g in data['groups'] if g['salesperson_name'] == 'Sin vendedor')
        self.assertEqual(unassigned_group['subtotal']['cta_cte_nd'], move2.amount_total)
        self.assertEqual(unassigned_group['subtotal']['dev_ctacte_dia_ant'], 50.0)

        self.assertEqual(data['grand_total']['contado'], move1.amount_total)
        self.assertEqual(data['grand_total']['cta_cte_nd'], move2.amount_total)
        self.assertEqual(data['grand_total']['dev_ctacte_dia_ant'], 50.0)

    def test_compute_data_filters_by_date(self):
        # A move posted for today must not leak into yesterday's report;
        # with no moves/payments on that other date, _compute_data raises.
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0)
        move.action_post()
        yesterday = fields.Date.subtract(self.today, days=1)
        with self.assertRaises(Exception):
            self.report_model._compute_data(yesterday, self.env.company)

    def test_compute_data_raises_when_empty(self):
        far_future = fields.Date.add(self.today, years=50)
        with self.assertRaises(Exception):
            self.report_model._compute_data(far_future, self.env.company)

    # -- Task 8: PDF rendering ---------------------------------------------

    def test_get_report_values_renders_html(self):
        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0)
        move.action_post()
        wizard = self.env['cash.closure.report.wizard'].create({
            'date': self.today,
            'company_id': self.env.company.id,
        })
        values = self.report_model._get_report_values(wizard.ids)
        self.assertIn('groups', values)
        self.assertEqual(values['date'], self.today)

        html, _report_type = self.env['ir.actions.report']._render_qweb_html(
            'sale_vendor_cash_closure.cash_closure_vendor', wizard.ids
        )
        self.assertIn(b'Cierre de Caja', html)

    # -- Task 9: wizard PDF action -----------------------------------------

    def test_wizard_action_print_pdf_returns_report_action(self):
        wizard = self.env['cash.closure.report.wizard'].create({
            'date': self.today,
            'company_id': self.env.company.id,
        })
        action = wizard.action_print_pdf()
        self.assertEqual(action['report_name'], 'sale_vendor_cash_closure.cash_closure_vendor')

    # -- Task 10: XLSX export ----------------------------------------------

    def test_wizard_action_export_xlsx_creates_readable_attachment(self):
        import base64
        import io
        from openpyxl import load_workbook

        move = self._create_move(self.partner_contado, doc_type=self.doc_type_normal, price_unit=100.0)
        move.invoice_user_id = self.env.user
        move.action_post()

        wizard = self.env['cash.closure.report.wizard'].create({
            'date': self.today,
            'company_id': self.env.company.id,
        })
        action = wizard.action_export_xlsx()
        self.assertEqual(action['type'], 'ir.actions.act_url')

        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'cash.closure.report.wizard'),
            ('res_id', '=', wizard.id),
        ], limit=1, order='id desc')
        self.assertTrue(attachment)

        workbook = load_workbook(io.BytesIO(base64.b64decode(attachment.datas)))
        sheet = workbook.active
        header_row = [cell.value for cell in sheet[1]]
        self.assertEqual(header_row[0], 'Comprobante')
        self.assertEqual(header_row[2], 'Contado')
