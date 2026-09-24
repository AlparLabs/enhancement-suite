from __future__ import annotations

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.alpardata_purchase_replacement_cost.tools import (
    cascade_equivalent_pct,
    compute_replacement_cost,
    parse_discount_cascade,
)


@tagged('post_install', '-at_install')
class TestDiscountCascade(BaseCase):

    def test_parse_simple(self):
        self.assertEqual(parse_discount_cascade('10+5+3'), [10.0, 5.0, 3.0])

    def test_parse_spaces_and_comma_decimal(self):
        self.assertEqual(parse_discount_cascade(' 10 + 2,5 '), [10.0, 2.5])
        self.assertEqual(parse_discount_cascade('7.5'), [7.5])

    def test_parse_empty(self):
        self.assertEqual(parse_discount_cascade(False), [])
        self.assertEqual(parse_discount_cascade(''), [])
        self.assertEqual(parse_discount_cascade('   '), [])

    def test_parse_invalid(self):
        for text in ('abc', '10++5', '10+', '+10', '100', '0', '-5', '10+105', '10;5'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_discount_cascade(text)

    def test_equivalent(self):
        self.assertAlmostEqual(cascade_equivalent_pct([10, 5, 3]), 17.065, places=6)
        self.assertEqual(cascade_equivalent_pct([]), 0.0)

    def test_formula_canonical_example(self):
        net, replacement = compute_replacement_cost(
            list_price=1000.0,
            discount_equivalent_pct=17.065,
            early_payment_pct=2.0,
            freight_pct=3.5,
            perception_pct=1.5,
            internal_tax_pct=0.0,
        )
        self.assertAlmostEqual(net, 829.35, places=6)
        self.assertAlmostEqual(replacement, 854.2305, places=6)

    def test_formula_zero_list(self):
        self.assertEqual(compute_replacement_cost(0.0, 10.0, 0, 0, 0, 0), (0.0, 0.0))
