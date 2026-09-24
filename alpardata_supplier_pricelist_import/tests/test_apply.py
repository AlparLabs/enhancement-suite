from __future__ import annotations

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import ImportCommon


@tagged('post_install', '-at_install')
class TestApply(ImportCommon):

    def test_apply_today(self):
        imp = self._file_import([['Código', 'Precio'], ['A1', 110], ['A2', 250]])
        imp.action_preview()
        self._line(imp, 'A2').to_apply = False
        imp.action_apply()
        self.assertEqual(imp.state, 'done')
        self.assertEqual(self.p1.product_tmpl_id.reference_cost, 110.0)
        self.assertEqual(self.p2.product_tmpl_id.reference_cost, 200.0)
        self.assertEqual(self.s1.date_end, fields.Date.today() - timedelta(days=1))
        history = self.env['product.supplierinfo.cost.history'].search([
            ('product_tmpl_id', '=', self.p1.product_tmpl_id.id),
        ], order='id desc', limit=1)
        self.assertIn(imp.name, history.change_reason)

    def test_apply_future_date(self):
        future = fields.Date.today() + timedelta(days=10)
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]], effective_date=future)
        imp.action_preview()
        imp.action_apply()
        self.assertEqual(self.p1.product_tmpl_id.reference_cost, 100.0)
        new_seller = self.p1.product_tmpl_id.seller_ids.filtered(lambda s: s.date_start == future)
        self.assertEqual(new_seller.reference_cost, 110.0)

    def test_apply_cascade_from_file(self):
        self.profile.col_cascade = 'Bonif'
        imp = self._file_import([['Código', 'Precio', 'Bonif'], ['A1', 100, '20']])
        imp.action_preview()
        imp.action_apply()
        tmpl = self.p1.product_tmpl_id
        seller = tmpl._get_reference_cost_seller()
        self.assertTrue(seller.use_own_conditions)
        self.assertEqual(seller.own_discount_cascade, '20')
        self.assertAlmostEqual(tmpl.replacement_cost, 80.0)

    def test_new_seller_keeps_code(self):
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]])
        imp.action_preview()
        imp.action_apply()
        seller = self.p1.product_tmpl_id._get_reference_cost_seller()
        self.assertEqual(seller.product_code, 'A1')

    def test_buyer_cannot_apply(self):
        buyer = new_test_user(self.env, login='buyer_spl', groups='purchase.group_purchase_user')
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]])
        imp.action_preview()
        with self.assertRaises(AccessError):
            imp.with_user(buyer).action_apply()

    def test_apply_requires_preview(self):
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]])
        with self.assertRaises(UserError):
            imp.action_apply()

    def test_cancel(self):
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]])
        imp.action_cancel()
        self.assertEqual(imp.state, 'cancelled')
