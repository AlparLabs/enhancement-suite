from __future__ import annotations

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import ReplacementCostCommon


@tagged('post_install', '-at_install')
class TestCommercialConditionsAccess(ReplacementCostCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.buyer = new_test_user(cls.env, login='buyer_rc', groups='purchase.group_purchase_user')
        cls.manager = new_test_user(cls.env, login='manager_rc', groups='purchase.group_purchase_manager')

    def test_buyer_cannot_edit_partner_conditions(self):
        with self.assertRaises(AccessError):
            self.partner.with_user(self.buyer).purchase_discount_cascade = '10'

    def test_buyer_can_edit_other_partner_fields(self):
        self.partner.with_user(self.buyer).write({'phone': '1234'})

    def test_manager_can_edit(self):
        self.partner.with_user(self.manager).purchase_discount_cascade = '10'
        self.assertEqual(self.partner.purchase_discount_cascade, '10')

    def test_buyer_cannot_set_own_conditions(self):
        seller = self._add_seller()
        with self.assertRaises(AccessError):
            seller.with_user(self.buyer).use_own_conditions = True

    def test_buyer_can_create_product_in_taxed_category(self):
        """El valor computado desde la categoría no cuenta como edición manual."""
        self.categ.internal_tax_pct = 8.0
        product = self.env['product.template'].with_user(self.buyer).create({
            'name': 'Creado por comprador', 'categ_id': self.categ.id,
        })
        self.assertEqual(product.internal_tax_pct, 8.0)

    def test_can_edit_flag(self):
        self.assertFalse(self.partner.with_user(self.buyer).can_edit_commercial_conditions)
        self.assertTrue(self.partner.with_user(self.manager).can_edit_commercial_conditions)
