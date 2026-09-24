from __future__ import annotations

from odoo.tests import tagged

from .common import ReplacementCostCommon


@tagged('post_install', '-at_install')
class TestReplacementCostPricelist(ReplacementCostCommon):

    def _pricelist(self, markup_pct):
        return self.env['product.pricelist'].create({
            'name': 'Lista Reposición Test',
            'currency_id': self.env.company.currency_id.id,
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'formula',
                'base': 'replacement_cost',
                # price_markup: recargo sobre la base (Odoo 17+)
                'price_markup': markup_pct,
            })],
        })

    def test_price_from_replacement_cost(self):
        self._set_partner_conditions()
        self._add_seller()
        pricelist = self._pricelist(40.0)
        price = pricelist._get_product_price(self.product, 1.0)
        self.assertAlmostEqual(price, 854.23 * 1.40, delta=0.02)

    def test_fallback_to_standard_price(self):
        pricelist = self._pricelist(0.0)
        price = pricelist._get_product_price(self.product, 1.0)
        self.assertAlmostEqual(price, 800.0, places=2)

    def test_reference_cost_base_unchanged(self):
        """La base existente sigue devolviendo la lista pura."""
        self._set_partner_conditions()
        self._add_seller()
        pricelist = self.env['product.pricelist'].create({
            'name': 'Lista Referencia Test',
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'formula',
                'base': 'reference_cost',
            })],
        })
        self.assertAlmostEqual(pricelist._get_product_price(self.product, 1.0), 1000.0, places=2)
