from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWarehouseAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.wh_a = cls.env['stock.warehouse'].create({
            'name': 'Sucursal A',
            'code': 'WHA',
            'company_id': cls.company.id,
        })
        cls.wh_b = cls.env['stock.warehouse'].create({
            'name': 'Sucursal B',
            'code': 'WHB',
            'company_id': cls.company.id,
        })
        cls.group_all = cls.env.ref(
            'stock_warehouse_user_access.group_warehouse_access_all'
        )
        cls.group_stock_user = cls.env.ref('stock.group_stock_user')
        cls.group_purchase_user = cls.env.ref('purchase.group_purchase_user')
        cls.user_a = cls._make_user('usuario_wh_a', cls.wh_a)
        cls.user_b = cls._make_user('usuario_wh_b', cls.wh_b)
        cls.user_none = cls._make_user('usuario_sin_wh', None)
        cls.user_all = cls._make_user('usuario_todo', None, all_access=True)
        cls.product = cls.env['product.product'].create({
            'name': 'Producto test',
            'is_storable': True,
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'Proveedor test'})

    @classmethod
    def _make_user(cls, login, warehouse, all_access=False):
        groups = cls.group_stock_user | cls.group_purchase_user
        if all_access:
            groups |= cls.group_all
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [(6, 0, groups.ids)],
            'warehouse_access_ids': [(6, 0, warehouse.ids if warehouse else [])],
            'default_warehouse_id': warehouse.id if warehouse else False,
        })

    def test_user_warehouse_fields(self):
        self.assertEqual(self.user_a.warehouse_access_ids, self.wh_a)
        self.assertEqual(self.user_a.default_warehouse_id, self.wh_a)
        self.assertFalse(self.user_none.warehouse_access_ids)

    def test_default_warehouse_must_be_allowed(self):
        with self.assertRaises(ValidationError):
            self.user_a.default_warehouse_id = self.wh_b

    def _make_picking(self, picking_type, location, location_dest):
        return self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location.id,
            'location_dest_id': location_dest.id,
        })

    def _visible_pickings(self, user):
        return self.env['stock.picking'].with_user(user).search([])

    def test_picking_of_own_warehouse_is_visible(self):
        picking = self._make_picking(
            self.wh_a.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_a.lot_stock_id,
        )
        self.assertIn(picking, self._visible_pickings(self.user_a))

    def test_picking_of_other_warehouse_is_hidden(self):
        picking = self._make_picking(
            self.wh_b.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_b.lot_stock_id,
        )
        self.assertNotIn(picking, self._visible_pickings(self.user_a))

    def test_inter_warehouse_transfer_visible_from_both_sides(self):
        picking = self._make_picking(
            self.wh_a.int_type_id,
            self.wh_a.lot_stock_id,
            self.wh_b.lot_stock_id,
        )
        self.assertIn(picking, self._visible_pickings(self.user_a))
        self.assertIn(picking, self._visible_pickings(self.user_b))

    def test_exempt_user_sees_every_picking(self):
        picking_a = self._make_picking(
            self.wh_a.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_a.lot_stock_id,
        )
        picking_b = self._make_picking(
            self.wh_b.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_b.lot_stock_id,
        )
        visible = self._visible_pickings(self.user_all)
        self.assertIn(picking_a, visible)
        self.assertIn(picking_b, visible)

    def test_user_without_warehouses_sees_no_picking(self):
        picking = self._make_picking(
            self.wh_a.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_a.lot_stock_id,
        )
        self.assertNotIn(picking, self._visible_pickings(self.user_none))

    def test_warehouse_access_invalidates_rule_cache(self):
        self.assertIn(
            'warehouse_access_ids',
            self.env['res.users']._get_invalidation_fields(),
        )

    def _make_purchase(self, picking_type):
        return self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'picking_type_id': picking_type.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
            })],
        })

    def _visible_purchases(self, user):
        return self.env['purchase.order'].with_user(user).search([])

    def _make_warehouseless_picking_type(self):
        return self.env['stock.picking.type'].create({
            'name': 'Recepción sin almacén',
            'sequence_code': 'SINWH',
            'code': 'incoming',
            'company_id': self.company.id,
            'warehouse_id': False,
            'default_location_src_id': self.env.ref('stock.stock_location_suppliers').id,
            'default_location_dest_id': self.wh_a.lot_stock_id.id,
        })

    def test_purchase_of_other_warehouse_is_hidden(self):
        order = self._make_purchase(self.wh_b.in_type_id)
        self.assertNotIn(order, self._visible_purchases(self.user_a))
        self.assertIn(order, self._visible_purchases(self.user_b))

    def test_purchase_without_warehouse_is_visible_to_everyone(self):
        order = self._make_purchase(self._make_warehouseless_picking_type())
        self.assertIn(order, self._visible_purchases(self.user_a))
        self.assertIn(order, self._visible_purchases(self.user_b))
        self.assertIn(order, self._visible_purchases(self.user_all))

    def test_exempt_user_sees_every_purchase(self):
        order_a = self._make_purchase(self.wh_a.in_type_id)
        order_b = self._make_purchase(self.wh_b.in_type_id)
        visible = self._visible_purchases(self.user_all)
        self.assertIn(order_a, visible)
        self.assertIn(order_b, visible)
