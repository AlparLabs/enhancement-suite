from __future__ import annotations

from odoo.tests import tagged

from .common import PriceWatchCommon


@tagged('post_install', '-at_install')
class TestTargetMarkup(PriceWatchCommon):

    def test_target_from_category(self):
        self.assertEqual(self.template.target_markup_pct, 40.0)

    def test_target_manual_override(self):
        self.template.target_markup_pct = 30.0
        self.assertEqual(self.template.target_markup_pct, 30.0)


@tagged('post_install', '-at_install')
class TestPriceWatchRefresh(PriceWatchCommon):

    def test_refresh_values(self):
        watch = self._watch()
        self.assertEqual(len(watch), 1)
        self.assertAlmostEqual(watch.shelf_price, 1694.0, places=2)
        self.assertAlmostEqual(watch.shelf_price_untaxed, 1400.0, places=2)
        self.assertAlmostEqual(watch.replacement_cost, 1000.0, places=2)
        self.assertAlmostEqual(watch.markup_pct, 40.0, places=2)
        self.assertEqual(watch.markup_alert, 'ok')

    def test_refresh_is_idempotent(self):
        first = self._watch()
        second = self._watch()
        self.assertEqual(first, second)

    def test_markup_below_target(self):
        self.seller.reference_cost = 1100.0  # recargo 27,27 %
        watch = self._watch()
        self.assertEqual(watch.markup_alert, 'below')

    def test_tolerance(self):
        self.seller.reference_cost = 1010.0  # recargo 38,6 %: dentro de 2 puntos
        self.assertEqual(self._watch().markup_alert, 'ok')

    def test_no_cost(self):
        template = self.env['product.template'].create({'name': 'Sin proveedor', 'sale_ok': True})
        self.assertEqual(self._watch(template).markup_alert, 'no_cost')

    def test_shelf_pricelist(self):
        pricelist = self.env['product.pricelist'].create({
            'name': 'Góndola test',
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'fixed',
                'fixed_price': 2000.0,
            })],
        })
        self.company.shelf_pricelist_id = pricelist
        self.assertAlmostEqual(self._watch().shelf_price, 2000.0, places=2)

    def test_per_company(self):
        other = self.env['res.company'].create({'name': 'Sucursal Góndola'})
        mine = self._watch()
        theirs = self.watch_model._refresh(self.template, other)
        self.assertNotEqual(mine, theirs)
        self.assertEqual(theirs.company_id, other)
