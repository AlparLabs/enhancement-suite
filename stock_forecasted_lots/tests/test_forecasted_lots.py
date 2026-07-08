from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestForecastedLots(TransactionCase):

    def setUp(self):
        super().setUp()
        self.warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.stock_location = self.warehouse.lot_stock_id
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
        self.report_model = self.env['stock.forecasted_product_product']

    def test_lots_ordered_by_available_quantity_ascending(self):
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, 100.0, lot_id=self.lot_a)
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, 30.0, lot_id=self.lot_b)

        data = self.report_model.with_context(
            warehouse_id=self.warehouse.id
        )._get_report_data(product_ids=self.product.ids)

        self.assertEqual(len(data['lots']), 2)
        self.assertEqual(data['lots'][0]['id'], self.lot_b.id)
        self.assertEqual(data['lots'][0]['available_quantity'], 30.0)
        self.assertEqual(data['lots'][1]['id'], self.lot_a.id)
        self.assertEqual(data['lots'][1]['available_quantity'], 100.0)

    def test_lots_filtered_by_warehouse(self):
        other_warehouse = self.env['stock.warehouse'].create({
            'name': 'Depot Test',
            'code': 'DEPT',
        })
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, 100.0, lot_id=self.lot_a)
        self.env['stock.quant']._update_available_quantity(
            self.product, other_warehouse.lot_stock_id, 50.0, lot_id=self.lot_b)

        data = self.report_model.with_context(
            warehouse_id=self.warehouse.id
        )._get_report_data(product_ids=self.product.ids)

        self.assertEqual([lot['id'] for lot in data['lots']], [self.lot_a.id])
