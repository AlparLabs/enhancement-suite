from __future__ import annotations

from odoo.tests import tagged

from odoo.addons.alpardata_price_change_labels import post_init_hook

from .common import PriceWatchCommon


@tagged('post_install', '-at_install')
class TestLabelQueue(PriceWatchCommon):

    def _print(self, fmt='3x8xprice', pricelist=None):
        wizard = self.env['product.label.layout'].create({
            'product_tmpl_ids': [(6, 0, self.template.ids)],
            'print_format': fmt,
            'pricelist_id': pricelist.id if pricelist else False,
        })
        wizard.process()

    def test_new_product_is_pending(self):
        self.assertTrue(self._watch().label_pending)

    def test_print_clears_pending(self):
        self._watch()
        self._print()
        watch = self._watch()
        self.assertFalse(watch.label_pending)
        self.assertAlmostEqual(watch.label_printed_price, 1694.0, places=2)
        self.assertTrue(watch.label_printed_date)

    def test_price_change_makes_pending(self):
        self._print()
        self.template.list_price = 1800.0
        watch = self._watch()
        self.assertTrue(watch.label_pending)
        self.assertAlmostEqual(watch.label_variation_pct, (1800 / 1694 - 1) * 100, places=2)

    def test_promo_does_not_clear(self):
        self._watch()
        self._print(fmt='3x8xpromo')
        self.assertTrue(self._watch().label_pending)

    def test_other_pricelist_keeps_pending(self):
        other = self.env['product.pricelist'].create({
            'name': 'Mayorista test',
            'item_ids': [(0, 0, {
                'applied_on': '3_global', 'compute_price': 'fixed', 'fixed_price': 1500.0,
            })],
        })
        self._print(pricelist=other)
        self.assertTrue(self._watch().label_pending)

    def test_post_init_hook_leaves_nothing_pending(self):
        post_init_hook(self.env)
        pending = self.watch_model.search([
            ('company_id', '=', self.company.id), ('label_pending', '=', True),
        ])
        self.assertFalse(pending)

    def test_cost_change_with_replacement_pricelist(self):
        """Regla con base reposición: sube el costo → sube el precio → etiqueta pendiente."""
        pricelist = self.env['product.pricelist'].create({
            'name': 'Góndola reposición',
            'item_ids': [(0, 0, {
                'applied_on': '3_global', 'compute_price': 'formula',
                'base': 'replacement_cost', 'price_markup': 69.4,
            })],
        })
        self.company.shelf_pricelist_id = pricelist
        self._print(pricelist=pricelist)
        self.assertFalse(self._watch().label_pending)
        self.seller.reference_cost = 1100.0
        self.assertTrue(self._watch().label_pending)
