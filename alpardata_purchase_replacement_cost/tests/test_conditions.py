from __future__ import annotations

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ReplacementCostCommon


@tagged('post_install', '-at_install')
class TestPartnerConditions(ReplacementCostCommon):

    def test_invalid_cascade_on_partner(self):
        with self.assertRaises(ValidationError):
            self.partner.purchase_discount_cascade = '10++5'

    def test_pct_out_of_range(self):
        for field in ('purchase_early_payment_pct', 'purchase_freight_pct',
                      'purchase_perception_pct'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.partner.write({field: 100.0})
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.partner.write({field: -1.0})

    def test_conditions_are_per_company(self):
        other = self.env['res.company'].create({'name': 'Otra Empresa Test'})
        self.partner.purchase_discount_cascade = '10'
        self.partner.with_company(other).purchase_discount_cascade = '20'
        self.assertEqual(self.partner.purchase_discount_cascade, '10')
        self.assertEqual(self.partner.with_company(other).purchase_discount_cascade, '20')

    def test_internal_tax_from_category(self):
        self.categ.internal_tax_pct = 8.0
        product = self.env['product.product'].create({
            'name': 'Nuevo', 'categ_id': self.categ.id,
        })
        self.assertEqual(product.internal_tax_pct, 8.0)

    def test_internal_tax_manual_override(self):
        self.categ.internal_tax_pct = 8.0
        product = self.env['product.product'].create({
            'name': 'Nuevo', 'categ_id': self.categ.id,
        })
        product.internal_tax_pct = 4.0
        self.assertEqual(product.internal_tax_pct, 4.0)

    def test_internal_tax_follows_category_change(self):
        other_categ = self.env['product.category'].create({
            'name': 'Tabaco Test', 'internal_tax_pct': 12.0,
        })
        self.template.categ_id = other_categ
        self.assertEqual(self.template.internal_tax_pct, 12.0)


@tagged('post_install', '-at_install')
class TestSupplierinfoConditions(ReplacementCostCommon):

    def test_inherits_partner_conditions(self):
        self._set_partner_conditions()
        seller = self._add_seller()
        self.assertEqual(seller.effective_discount_cascade, '10+5+3')
        self.assertEqual(seller.effective_early_payment_pct, 2.0)
        self.assertEqual(seller.effective_freight_pct, 3.5)
        self.assertEqual(seller.effective_perception_pct, 1.5)
        self.assertAlmostEqual(seller.discount_equivalent_pct, 17.065, places=6)

    def test_own_conditions_override(self):
        self._set_partner_conditions()
        seller = self._add_seller(
            use_own_conditions=True,
            own_discount_cascade='20',
            own_early_payment_pct=0.0,
            own_freight_pct=0.0,
            own_perception_pct=0.0,
        )
        self.assertEqual(seller.effective_discount_cascade, '20')
        self.assertEqual(seller.effective_freight_pct, 0.0)
        self.assertAlmostEqual(seller.replacement_cost, 800.0, places=6)

    def test_replacement_cost_canonical(self):
        self._set_partner_conditions()
        seller = self._add_seller()
        self.assertAlmostEqual(seller.replacement_cost, 854.2305, places=4)
        self.assertIn('Reposición', seller.replacement_cost_breakdown)
        self.assertIn('10+5+3', seller.replacement_cost_breakdown)

    def test_seller_company_conditions(self):
        """El supplierinfo de otra empresa toma las condiciones de esa empresa."""
        other = self.env['res.company'].create({'name': 'Empresa Seller Test'})
        self.partner.with_company(other).purchase_discount_cascade = '50'
        seller = self._add_seller(company_id=other.id)
        self.assertEqual(seller.effective_discount_cascade, '50')

    def test_invalid_own_cascade(self):
        with self.assertRaises(ValidationError):
            self._add_seller(use_own_conditions=True, own_discount_cascade='x')

