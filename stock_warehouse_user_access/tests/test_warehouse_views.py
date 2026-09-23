from ast import literal_eval

from odoo.addons.stock_warehouse_user_access.models.ir_actions import QTY_CONTEXT_KEY

from .common import WarehouseAccessCommon


class TestWarehouseViews(WarehouseAccessCommon):
    """Filtro de interfaz de reportes, reabastecimiento y ajustes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.Quant = cls.env['stock.quant']
        cls.Quant._update_available_quantity(cls.product, cls.wh_a.lot_stock_id, 5)
        cls.Quant._update_available_quantity(cls.product, cls.wh_b.lot_stock_id, 7)
        cls.quant_a = cls.Quant._gather(cls.product, cls.wh_a.lot_stock_id)
        cls.quant_b = cls.Quant._gather(cls.product, cls.wh_b.lot_stock_id)
        cls.user_ab = cls._make_user('usuario_wh_ab', cls.wh_a)
        cls.user_ab.warehouse_access_ids = cls.wh_a | cls.wh_b

    def _action_records(self, user, xml_id):
        action = self.env['ir.actions.actions'].with_user(user)._for_xml_id(xml_id)
        return self._records_in(action)

    def _records_in(self, action):
        domain = action.get('domain') or []
        if isinstance(domain, str):
            domain = literal_eval(domain)
        return self.env[action['res_model']].search(domain)

    def _make_move(self, location, location_dest):
        return self.env['stock.move'].create({
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 1.0,
            'location_id': location.id,
            'location_dest_id': location_dest.id,
        })

    # Ajustes: inventario físico y ubicaciones

    def test_physical_inventory_shows_only_own_warehouse(self):
        action = self.Quant.with_user(self.user_a).action_view_inventory()
        quants = self._records_in(action)
        self.assertIn(self.quant_a, quants)
        self.assertNotIn(self.quant_b, quants)

    def test_quants_report_shows_only_own_warehouse(self):
        action = self.Quant.with_user(self.user_a).action_view_quants()
        quants = self._records_in(action)
        self.assertIn(self.quant_a, quants)
        self.assertNotIn(self.quant_b, quants)

    def test_physical_inventory_unfiltered_for_exempt_user(self):
        action = self.Quant.with_user(self.user_all).action_view_inventory()
        quants = self._records_in(action)
        self.assertIn(self.quant_a, quants)
        self.assertIn(self.quant_b, quants)

    def test_physical_inventory_empty_without_warehouses(self):
        action = self.Quant.with_user(self.user_none).action_view_inventory()
        quants = self._records_in(action)
        self.assertNotIn(self.quant_a, quants)
        self.assertNotIn(self.quant_b, quants)

    def test_scrap_shows_only_own_warehouse(self):
        Scrap = self.env['stock.scrap']
        scrap_a = Scrap.create({
            'product_id': self.product.id,
            'location_id': self.wh_a.lot_stock_id.id,
        })
        scrap_b = Scrap.create({
            'product_id': self.product.id,
            'location_id': self.wh_b.lot_stock_id.id,
        })
        scraps = self._action_records(self.user_a, 'stock.action_stock_scrap')
        self.assertIn(scrap_a, scraps)
        self.assertNotIn(scrap_b, scraps)

    # Reabastecimiento

    def test_replenishment_shows_only_own_warehouse(self):
        Orderpoint = self.env['stock.warehouse.orderpoint']
        orderpoint_a = Orderpoint.create({
            'product_id': self.product.id,
            'warehouse_id': self.wh_a.id,
            'location_id': self.wh_a.lot_stock_id.id,
        })
        orderpoint_b = Orderpoint.create({
            'product_id': self.product.id,
            'warehouse_id': self.wh_b.id,
            'location_id': self.wh_b.lot_stock_id.id,
        })
        orderpoints = self._action_records(
            self.user_a, 'stock.action_orderpoint_replenish'
        )
        self.assertIn(orderpoint_a, orderpoints)
        self.assertNotIn(orderpoint_b, orderpoints)
        self.assertEqual(
            orderpoints & (orderpoint_a | orderpoint_b), orderpoint_a,
        )

    # Reportes: movimientos

    def test_moves_analysis_shows_only_own_warehouse(self):
        move_a = self._make_move(self.supplier_location, self.wh_a.lot_stock_id)
        move_b = self._make_move(self.supplier_location, self.wh_b.lot_stock_id)
        moves = self._action_records(self.user_a, 'stock.stock_move_action')
        self.assertIn(move_a, moves)
        self.assertNotIn(move_b, moves)

    def test_moves_analysis_inter_warehouse_visible_from_both_sides(self):
        move = self._make_move(self.wh_a.lot_stock_id, self.wh_b.lot_stock_id)
        self.assertIn(move, self._action_records(self.user_a, 'stock.stock_move_action'))
        self.assertIn(move, self._action_records(self.user_b, 'stock.stock_move_action'))

    def test_moves_history_shows_only_own_warehouse(self):
        move_a = self._make_move(self.supplier_location, self.wh_a.lot_stock_id)
        move_b = self._make_move(self.supplier_location, self.wh_b.lot_stock_id)
        (move_a | move_b)._action_confirm()
        (move_a | move_b)._action_assign()
        lines = self._action_records(self.user_a, 'stock.stock_move_line_action')
        self.assertTrue(move_a.move_line_ids)
        self.assertLessEqual(move_a.move_line_ids, lines)
        self.assertFalse(move_b.move_line_ids & lines)

    def test_moves_analysis_unfiltered_for_exempt_user(self):
        action = self.env['ir.actions.actions'].with_user(
            self.user_all
        )._for_xml_id('stock.stock_move_action')
        self.assertFalse(action.get('domain'))

    # Reportes: existencias

    def _qty(self, user, **context):
        # qty_available se cachea por las claves de depends_context, que no
        # incluyen al usuario ni la clave del reporte. En el cliente web cada
        # lectura es una request nueva; acá hay que invalidar a mano.
        self.env.invalidate_all()
        return self.product.with_user(user).with_context(**context).qty_available

    def test_stock_report_action_marks_context_for_restricted_user(self):
        action = self.env['ir.actions.actions'].with_user(
            self.user_a
        )._for_xml_id('stock.action_product_stock_view')
        self.assertTrue(literal_eval(action['context']).get(QTY_CONTEXT_KEY))

    def test_stock_report_action_untouched_for_exempt_user(self):
        action = self.env['ir.actions.actions'].with_user(
            self.user_all
        )._for_xml_id('stock.action_product_stock_view')
        self.assertNotIn(QTY_CONTEXT_KEY, action.get('context') or '')

    def test_stock_report_qty_only_own_warehouse(self):
        self.assertEqual(self._qty(self.user_a, **{QTY_CONTEXT_KEY: True}), 5)

    def test_qty_unchanged_outside_stock_report(self):
        self.assertEqual(self._qty(self.user_a), 12)

    def test_stock_report_qty_unfiltered_for_exempt_user(self):
        self.assertEqual(self._qty(self.user_all, **{QTY_CONTEXT_KEY: True}), 12)

    def test_stock_report_cannot_query_foreign_warehouse(self):
        qty = self._qty(self.user_a, **{
            QTY_CONTEXT_KEY: True, 'search_warehouse': self.wh_b.id,
        })
        self.assertEqual(qty, 0)

    def test_stock_report_respects_filter_within_allowed(self):
        qty = self._qty(self.user_ab, **{
            QTY_CONTEXT_KEY: True, 'search_warehouse': self.wh_b.id,
        })
        self.assertEqual(qty, 7)
