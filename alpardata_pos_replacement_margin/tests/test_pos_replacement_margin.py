from __future__ import annotations

import odoo
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@odoo.tests.tagged('post_install', '-at_install')
class TestPosReplacementMargin(TestPoSCommon):

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        vendor = self.env['res.partner'].create({
            'name': 'Proveedor POS', 'purchase_discount_cascade': '10',
        })
        # precio 10, AVCO 5, lista 6 → reposición 5,40
        self.product = self.create_product('Galletitas', self.categ_basic, 10, 5)
        self.env['product.supplierinfo'].create({
            'partner_id': vendor.id,
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'price': 6.0,
            'reference_cost': 6.0,
        })

    def _sync(self, lines):
        self.open_new_session()
        self.env['pos.order'].sync_from_ui([self.create_ui_order_data(lines)])
        return self.pos_session.order_ids[0]

    def test_sale(self):
        order = self._sync([(self.product, 2)])
        line = order.lines
        self.assertAlmostEqual(line.replacement_cost_unit, 5.4, places=4)
        self.assertAlmostEqual(line.replacement_margin, 20.0 - 10.8, places=4)
        self.assertAlmostEqual(order.replacement_margin, 9.2, places=4)

    def test_refund_is_negative(self):
        order = self._sync([(self.product, -1)])
        self.assertAlmostEqual(order.lines.replacement_margin, -10.0 + 5.4, places=4)

    def test_report(self):
        order = self._sync([(self.product, 2)])
        self.env.flush_all()
        data = self.env['report.pos.order']._read_group(
            [('order_id', '=', order.id)], [], ['replacement_margin:sum'],
        )
        self.assertAlmostEqual(data[0][0], 9.2, places=2)
