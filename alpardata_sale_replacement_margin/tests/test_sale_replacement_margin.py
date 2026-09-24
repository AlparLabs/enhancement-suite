from __future__ import annotations

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSaleReplacementMargin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente Test'})
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Proveedor Test', 'purchase_discount_cascade': '10',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Aceite 1L',
            'standard_price': 700.0,
            'list_price': 1500.0,
            'taxes_id': [(5, 0, 0)],
        })
        cls.seller = cls.env['product.supplierinfo'].create({
            'partner_id': cls.vendor.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'price': 1000.0,
            'reference_cost': 1000.0,  # reposición = 900 (bonif. 10)
        })

    def _order(self, qty=2.0, uom=None, currency=None):
        vals = {'partner_id': self.customer.id}
        if currency:
            pricelist = self.env['product.pricelist'].create({
                'name': f'Lista {currency.name}', 'currency_id': currency.id,
            })
            vals['pricelist_id'] = pricelist.id
        line = {'product_id': self.product.id, 'product_uom_qty': qty, 'price_unit': 1500.0}
        if uom:
            line['product_uom_id'] = uom.id
        vals['order_line'] = [(0, 0, line)]
        return self.env['sale.order'].create(vals)

    def test_line_values(self):
        order = self._order()
        line = order.order_line
        self.assertAlmostEqual(line.replacement_cost_unit, 900.0, places=2)
        self.assertFalse(line.replacement_cost_fallback)
        self.assertAlmostEqual(line.replacement_margin, 3000.0 - 1800.0, places=2)
        self.assertAlmostEqual(line.replacement_margin_percent, 0.4, places=4)
        self.assertAlmostEqual(order.replacement_margin, 1200.0, places=2)
        self.assertAlmostEqual(order.replacement_margin_percent, 0.4, places=4)

    def test_standard_margin_untouched(self):
        line = self._order().order_line
        self.assertAlmostEqual(line.purchase_price, 700.0, places=2)
        self.assertAlmostEqual(line.margin, 3000.0 - 1400.0, places=2)

    def test_line_uom_dozen(self):
        dozen = self.env.ref('uom.product_uom_dozen')
        line = self._order(qty=1.0, uom=dozen).order_line
        self.assertAlmostEqual(line.replacement_cost_unit, 900.0 * 12, places=2)

    def test_order_in_usd(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        if self.env.company.currency_id == usd:
            self.skipTest('La empresa de test ya usa USD')
        self.env['res.currency.rate'].create({
            'currency_id': usd.id, 'company_id': self.env.company.id,
            'name': fields.Date.today(), 'rate': 1 / 1000,
        })
        line = self._order(currency=usd).order_line
        self.assertAlmostEqual(line.replacement_cost_unit, 0.9, places=4)

    def test_fallback_to_avco(self):
        self.seller.unlink()
        line = self._order().order_line
        self.assertTrue(line.replacement_cost_fallback)
        self.assertAlmostEqual(line.replacement_cost_unit, 700.0, places=2)

    def test_recomputed_on_confirm(self):
        order = self._order()
        self.seller.reference_cost = 1200.0  # reposición 1080
        self.assertAlmostEqual(order.order_line.replacement_cost_unit, 900.0, places=2)
        order.action_confirm()
        self.assertAlmostEqual(order.order_line.replacement_cost_unit, 1080.0, places=2)
        self.assertAlmostEqual(order.replacement_margin, 3000.0 - 2160.0, places=2)
