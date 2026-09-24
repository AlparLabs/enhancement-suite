from __future__ import annotations

from odoo.tests import tagged

from .common import ReplacementCostCommon


@tagged('post_install', '-at_install')
class TestPurchaseOrderCascade(ReplacementCostCommon):

    def _order(self):
        return self.env['purchase.order'].create({'partner_id': self.partner.id})

    def _line(self, po):
        return self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': self.product.id,
            'product_qty': 1.0,
        })

    def test_manual_line_gets_cascade(self):
        self._set_partner_conditions()
        self._add_seller()
        line = self._line(self._order())
        self.assertEqual(line.price_unit, 1000.0)
        self.assertAlmostEqual(line.discount, 17.065, places=2)
        self.assertEqual(line.discount_cascade, '10+5+3')

    def test_without_cascade_uses_supplierinfo_discount(self):
        self._set_partner_conditions(cascade='')
        self._add_seller(discount=7.0)
        line = self._line(self._order())
        self.assertEqual(line.discount, 7.0)
        self.assertFalse(line.discount_cascade)

    def test_manual_price_not_touched(self):
        self._set_partner_conditions()
        self._add_seller()
        line = self._line(self._order())
        line.write({'price_unit': 900.0, 'discount': 0.0})
        line.product_qty = 2.0
        self.assertEqual(line.price_unit, 900.0)
        self.assertEqual(line.discount, 0.0)

    def test_catalog_path(self):
        self._set_partner_conditions()
        self._add_seller()
        po = self._order()
        po._update_order_line_info(self.product.id, 1.0)
        line = po.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertAlmostEqual(line.discount, 17.065, places=2)
        self.assertEqual(line.discount_cascade, '10+5+3')

    def test_replenishment_path(self):
        self._set_partner_conditions()
        self._add_seller()
        po = self._order()
        vals = self.env['purchase.order.line']._prepare_purchase_order_line(
            self.product, 1.0, self.product.uom_id, self.env.company, self.partner, po,
        )
        self.assertAlmostEqual(vals['discount'], 17.065, places=2)
        self.assertEqual(vals['discount_cascade'], '10+5+3')
