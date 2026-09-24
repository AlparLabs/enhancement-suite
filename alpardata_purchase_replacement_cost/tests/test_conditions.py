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
