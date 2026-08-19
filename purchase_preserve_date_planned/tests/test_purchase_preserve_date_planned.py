from datetime import timedelta
from odoo import fields
from odoo.tests.common import TransactionCase


class TestPurchasePreserveDatePlanned(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Vendor Test Preserve Date',
        })
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')

        cls.product_10_days = cls.env['product.product'].create({
            'name': 'Product with 10 Days Lead Time',
            'type': 'consu',
            'seller_ids': [(0, 0, {
                'partner_id': cls.partner.id,
                'min_qty': 1,
                'price': 100.0,
                'delay': 10,
            })],
        })

        cls.product_2_days = cls.env['product.product'].create({
            'name': 'Product with 2 Days Lead Time',
            'type': 'consu',
            'seller_ids': [(0, 0, {
                'partner_id': cls.partner.id,
                'min_qty': 1,
                'price': 50.0,
                'delay': 2,
            })],
        })

    def test_new_line_gets_default_lead_time_date(self):
        """When creating a new line without order date_planned, standard calculates date_planned using seller delay."""
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_10_days.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
            })],
        })
        line = po.order_line[0]
        expected_date = (po.date_order + timedelta(days=10)).date()
        self.assertEqual(line.date_planned.date(), expected_date)

    def test_new_line_inherits_existing_order_date_planned(self):
        """Adding a new product to a PO with an established date_planned must inherit the PO date and not overwrite header date_planned."""
        po_date = fields.Datetime.now() + timedelta(days=45)
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_10_days.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
                'date_planned': po_date,
            })],
        })
        self.assertEqual(po.date_planned, po_date)

        # Add a new line with product_2_days (delay 2 days)
        # Without our fix, this line would get now + 2 days, pulling po.date_planned down to now + 2 days
        line_2 = self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': self.product_2_days.id,
            'product_qty': 1.0,
            'price_unit': 50.0,
        })

        self.assertEqual(line_2.date_planned, po_date, 'New line did not inherit the order date_planned')
        self.assertEqual(po.date_planned, po_date, 'Order header date_planned was rewritten when adding a new product')

    def test_modify_qty_preserves_manual_date_planned(self):
        """Modifying product_qty must not overwrite a manually set date_planned."""
        manual_date = fields.Datetime.now() + timedelta(days=45)
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_10_days.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
                'date_planned': manual_date,
            })],
        })
        line = po.order_line[0]
        self.assertEqual(line.date_planned, manual_date)

        # Modify quantity (which in standard Odoo would trigger _compute_price_unit_and_date_planned_and_name and reset date_planned)
        line.product_qty = 10.0
        self.assertEqual(line.date_planned, manual_date, 'Manual date_planned was overwritten after changing product_qty')

    def test_modify_uom_preserves_manual_date_planned(self):
        """Modifying product_uom must not overwrite an existing date_planned."""
        manual_date = fields.Datetime.now() + timedelta(days=60)
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_10_days.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
                'product_uom': self.uom_unit.id,
                'date_planned': manual_date,
            })],
        })
        line = po.order_line[0]
        self.assertEqual(line.date_planned, manual_date)

        # Modify UoM
        line.product_uom = self.uom_dozen.id
        self.assertEqual(line.date_planned, manual_date, 'Manual date_planned was overwritten after changing product_uom')

    def test_po_header_date_planned_propagates_and_is_preserved(self):
        """Setting date_planned on PO header updates lines and is preserved upon subsequent qty changes."""
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_10_days.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
            })],
        })
        line = po.order_line[0]

        # Update PO header date_planned
        header_date = fields.Datetime.now() + timedelta(days=90)
        po.date_planned = header_date
        po.onchange_date_planned()
        self.assertEqual(line.date_planned, header_date)

        # Modify qty on line
        line.product_qty = 5.0
        self.assertEqual(line.date_planned, header_date, 'Header-propagated date_planned was overwritten after changing product_qty')
