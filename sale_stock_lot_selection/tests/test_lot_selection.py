from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestLotSelection(TransactionCase):

    def setUp(self):
        super().setUp()
        self.warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.stock_location = self.warehouse.lot_stock_id
        self.partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        self.product = self.env['product.product'].create({
            'name': 'Cable 2mm',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
        })
        self.lot_a = self.env['stock.lot'].create({
            'name': 'BOBINA-A',
            'product_id': self.product.id,
        })
        self.lot_b = self.env['stock.lot'].create({
            'name': 'BOBINA-B',
            'product_id': self.product.id,
        })
        # Manual reservation so tests can prove OUR override triggers the
        # reservation at confirm (and that nothing is forced without selection).
        self.warehouse.out_type_id.reservation_method = 'manual'

    def _add_stock(self, lot, qty):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, qty, lot_id=lot)

    def _create_order(self, qty=100.0, requested=None, product=None):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse.id,
            'order_line': [(0, 0, {
                'product_id': (product or self.product).id,
                'product_uom_qty': qty,
            })],
        })
        line = order.order_line
        if requested:
            line.requested_lot_ids = [
                (0, 0, {'lot_id': lot.id, 'quantity': lot_qty})
                for lot, lot_qty in requested
            ]
        return order, line

    def test_sum_exceeding_line_qty_raises(self):
        with self.assertRaises(ValidationError):
            self._create_order(
                qty=100.0,
                requested=[(self.lot_a, 60.0), (self.lot_b, 60.0)])

    def test_lot_of_other_product_raises(self):
        other_product = self.env['product.product'].create({
            'name': 'Cable 4mm',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
        })
        other_lot = self.env['stock.lot'].create({
            'name': 'BOBINA-X',
            'product_id': other_product.id,
        })
        with self.assertRaises(ValidationError):
            self._create_order(qty=50.0, requested=[(other_lot, 10.0)])

    def test_zero_quantity_raises(self):
        with self.assertRaises(ValidationError):
            self._create_order(qty=50.0, requested=[(self.lot_a, 0.0)])

    def test_lot_selection_status(self):
        _, line = self._create_order(qty=50.0)
        self.assertEqual(line.lot_selection_status, 'pending')
        line.requested_lot_ids = [(0, 0, {'lot_id': self.lot_a.id, 'quantity': 50.0})]
        self.assertEqual(line.lot_selection_status, 'selected')
        untracked = self.env['product.product'].create({
            'name': 'Cinta aislante',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'none',
        })
        _, untracked_line = self._create_order(qty=5.0, product=untracked)
        self.assertEqual(untracked_line.lot_selection_status, 'not_applicable')

    def test_requested_lot_reserved_on_confirm(self):
        self._add_stock(self.lot_a, 100.0)
        self._add_stock(self.lot_b, 100.0)
        order, line = self._create_order(
            qty=80.0, requested=[(self.lot_b, 80.0)])
        order.action_confirm()
        move_lines = line.move_ids.move_line_ids
        self.assertEqual(move_lines.lot_id, self.lot_b)
        self.assertEqual(sum(move_lines.mapped('quantity_product_uom')), 80.0)
        self.assertEqual(line.move_ids.state, 'assigned')

    def test_insufficient_requested_lot_falls_back(self):
        self._add_stock(self.lot_a, 100.0)
        self._add_stock(self.lot_b, 30.0)
        order, line = self._create_order(
            qty=80.0, requested=[(self.lot_b, 80.0)])
        order.action_confirm()
        by_lot = {ml.lot_id: ml.quantity_product_uom
                  for ml in line.move_ids.move_line_ids}
        self.assertEqual(by_lot.get(self.lot_b), 30.0)
        self.assertEqual(by_lot.get(self.lot_a), 50.0)
        self.assertEqual(line.move_ids.state, 'assigned')

    def test_split_across_two_requested_lots(self):
        self._add_stock(self.lot_a, 100.0)
        self._add_stock(self.lot_b, 100.0)
        order, line = self._create_order(
            qty=100.0, requested=[(self.lot_b, 60.0), (self.lot_a, 40.0)])
        order.action_confirm()
        by_lot = {ml.lot_id: ml.quantity_product_uom
                  for ml in line.move_ids.move_line_ids}
        self.assertEqual(by_lot.get(self.lot_b), 60.0)
        self.assertEqual(by_lot.get(self.lot_a), 40.0)

    def test_no_selection_keeps_native_behavior(self):
        self._add_stock(self.lot_a, 100.0)
        order, line = self._create_order(qty=50.0)
        order.action_confirm()
        # reservation_method='manual' and no requested lots: nothing must be
        # forced — the move stays confirmed with no move lines, exactly as
        # native Odoo behaves.
        self.assertEqual(line.move_ids.state, 'confirmed')
        self.assertFalse(line.move_ids.move_line_ids)

    def test_wizard_prefills_available_lots(self):
        self._add_stock(self.lot_a, 100.0)
        self._add_stock(self.lot_b, 30.0)
        _, line = self._create_order(qty=80.0)
        wizard = self.env['sale.line.lot.selection'].with_context(
            default_sale_line_id=line.id).create({})
        # Prefilled from stock_forecasted_lots: ascending availability.
        self.assertEqual(
            wizard.line_ids.mapped('lot_id'), self.lot_b | self.lot_a)
        self.assertEqual(
            wizard.line_ids.mapped('available_quantity'), [30.0, 100.0])
        self.assertEqual(
            wizard.line_ids.mapped('quantity_to_take'), [0.0, 0.0])

    def test_wizard_apply_writes_requested_lots(self):
        self._add_stock(self.lot_a, 100.0)
        self._add_stock(self.lot_b, 30.0)
        _, line = self._create_order(qty=80.0)
        wizard = self.env['sale.line.lot.selection'].with_context(
            default_sale_line_id=line.id).create({})
        wizard.line_ids.filtered(
            lambda l: l.lot_id == self.lot_b).quantity_to_take = 30.0
        wizard.action_apply()
        self.assertEqual(line.requested_lot_ids.lot_id, self.lot_b)
        self.assertEqual(line.requested_lot_ids.quantity, 30.0)
        self.assertEqual(line.lot_selection_status, 'selected')
