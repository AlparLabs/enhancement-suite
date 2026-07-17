# Sale Stock Lot Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline execution chosen for this plan). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sale_stock_lot_selection` so a salesperson can optionally pick specific lots (and quantities) on a lot-tracked sale order line via a popup, have those lots reserved immediately on order confirmation, and fall back 100% to Odoo's native reservation for anything not covered.

**Architecture:** A new persistent model `sale.order.line.lot` stores the salesperson's lot requests per line. A `stock.move._action_assign()` override reserves requested lots first (via the native `_update_reserved_quantity(need, location, lot_id=...)` hook, which caps at real availability), then delegates to `super()` which fills the remainder with the native removal strategy — `super()` *is* the fallback. A `sale.order.action_confirm()` override forces `_action_assign()` on the affected moves right after confirmation. A transient wizard, prefilled from `stock_forecasted_lots`' `_get_lots_data()`, is the selection UI; a computed 3-state field drives the visual indicator (nothing / warning / success badge).

**Tech Stack:** Odoo 19.0 (Python ORM, XML views), depends on `sale_stock` + `stock_forecasted_lots`.

**Spec:** `docs/superpowers/specs/2026-07-17-sale-stock-lot-selection-design.md`

**Verified Odoo 19 facts (from odoo/odoo 19.0 source, do not re-derive):**
- `stock.move._action_assign(self, force_qty=False)` — for moves without `move_orig_ids` and `procure_method != 'make_to_order'`, computes `need` and calls `move._update_reserved_quantity(need, move.location_id, strict=False)`. It reads reserved qty as `move.quantity` (in move UoM) and compares to `move.product_uom_qty`.
- `stock.move._update_reserved_quantity(self, need, location_id, lot_id=None, package_id=None, owner_id=None, strict=True)` — reserves from quants (capped at what's actually available for that lot/location), creates the move lines, returns `taken_quantity` (in product UoM). With `lot_id` and `strict=False` it reserves from that lot's quants in the location subtree (plus lot-less quants, which for a lot-tracked product only exist as data anomalies — acceptable).
- `stock.move._should_bypass_reservation()` and `move.picked` exist as used below.
- `sale_stock` defines `sale_line_id = fields.Many2one('sale.order.line', ...)` on `stock.move`, and `sale.order.line.move_ids` (inverse).
- Sale line UoM field in 19 is `product_uom_id`; quantity is `product_uom_qty`. `stock.warehouse` is on `sale.order.warehouse_id` (from `sale_stock`).
- `stock_forecasted_lots` provides `stock.forecasted_product_product._get_lots_data(product_template_ids, product_ids, warehouse)` returning `[{'id', 'display_name', 'product_display_name', 'quantity', 'reserved_quantity', 'available_quantity', 'uom'}, ...]` sorted ascending by `available_quantity`.
- Odoo 19 translation helper in Python: `self.env._("...")`.
- No Odoo runtime exists in this sandbox: every "run test" step means `python3 -m py_compile` + manual trace; real execution happens on the client instance/CI (same protocol as `stock_forecasted_lots`).

---

## Task 1: Scaffold + security

**Files:**
- Create: `sale_stock_lot_selection/__init__.py`
- Create: `sale_stock_lot_selection/__manifest__.py`
- Create: `sale_stock_lot_selection/models/__init__.py`
- Create: `sale_stock_lot_selection/wizard/__init__.py`
- Create: `sale_stock_lot_selection/security/ir.model.access.csv`

- [ ] **Step 1: Root `__init__.py`**

```python
from . import models
from . import wizard
```

- [ ] **Step 2: Manifest**

```python
{
    'name': 'Sale Stock Lot Selection',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Let the salesperson pick the lots to deliver from the sale order line',
    'description': """
        On a lot-tracked sale order line, the salesperson can open a popup
        listing the available lots of the order's warehouse and choose which
        lot(s) — and how much of each — to deliver. On order confirmation
        those lots are reserved immediately on the delivery. Anything not
        covered by the selection (or no longer available) falls back to
        Odoo's native automatic reservation strategy.
        A visual badge on the line shows whether a lot-tracked product still
        has no lot selected.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'stock_forecasted_lots'],
    'data': [
        'security/ir.model.access.csv',
        'views/lot_selection_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

- [ ] **Step 3: `models/__init__.py`**

```python
from . import sale_order
from . import sale_order_line
from . import sale_order_line_lot
from . import stock_move
```

- [ ] **Step 4: `wizard/__init__.py`**

```python
from . import lot_selection_wizard
```

- [ ] **Step 5: `security/ir.model.access.csv`**

Sales users get full CRUD on the requested-lot model and the wizard; stock users get read on the requested-lot model (the `_action_assign` override reads it when an inventory user reserves a picking).

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sale_order_line_lot_sale_user,sale.order.line.lot sale user,model_sale_order_line_lot,sales_team.group_sale_salesman,1,1,1,1
access_sale_order_line_lot_stock_user,sale.order.line.lot stock user,model_sale_order_line_lot,stock.group_stock_user,1,0,0,0
access_sale_line_lot_selection_sale_user,sale.line.lot.selection sale user,model_sale_line_lot_selection,sales_team.group_sale_salesman,1,1,1,1
access_sale_line_lot_selection_line_sale_user,sale.line.lot.selection.line sale user,model_sale_line_lot_selection_line,sales_team.group_sale_salesman,1,1,1,1
```

- [ ] **Step 6: Commit**

Note: the module is not installable until Tasks 2-6 create the imported files and views — same intentional pattern as the previous module's scaffold.

```bash
git add sale_stock_lot_selection/
git commit -m "feat(sale_stock_lot_selection): scaffold module"
```

---

## Task 2: Requested-lot model + sale line extension (constraints & visual status)

**Files:**
- Create: `sale_stock_lot_selection/models/sale_order_line_lot.py`
- Create: `sale_stock_lot_selection/models/sale_order_line.py`
- Create: `sale_stock_lot_selection/tests/__init__.py`
- Create: `sale_stock_lot_selection/tests/test_lot_selection.py`

- [ ] **Step 1: Write the failing tests**

`tests/__init__.py`:

```python
from . import test_lot_selection
```

`tests/test_lot_selection.py` — setUp shared by the whole suite plus the first 4 tests (constraints + status):

```python
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
```

- [ ] **Step 2: Verify the tests fail**

No runtime: `python3 -m py_compile sale_stock_lot_selection/tests/test_lot_selection.py` (syntax only) + note the tests would fail with `Invalid field 'requested_lot_ids'` since the model doesn't exist yet.

- [ ] **Step 3: Implement `models/sale_order_line_lot.py`**

```python
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrderLineLot(models.Model):
    _name = 'sale.order.line.lot'
    _description = "Requested Lot on Sale Order Line"

    sale_line_id = fields.Many2one(
        'sale.order.line', string="Sale Line", required=True,
        ondelete='cascade', index=True)
    lot_id = fields.Many2one(
        'stock.lot', string="Lot", required=True, ondelete='restrict')
    quantity = fields.Float(
        string="Quantity", required=True, digits='Product Unit',
        help="Quantity to take from this lot, in the product's unit of measure.")

    _sql_constraints = [
        ('lot_per_line_uniq', 'unique(sale_line_id, lot_id)',
         'The same lot cannot be requested twice on the same line.'),
    ]

    @api.constrains('lot_id', 'sale_line_id')
    def _check_lot_matches_product(self):
        for record in self:
            if record.lot_id.product_id != record.sale_line_id.product_id:
                raise ValidationError(self.env._(
                    "Lot %(lot)s does not belong to product %(product)s.",
                    lot=record.lot_id.display_name,
                    product=record.sale_line_id.product_id.display_name))

    @api.constrains('quantity')
    def _check_quantity_positive(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(self.env._(
                    "The requested lot quantity must be greater than zero."))

    @api.constrains('quantity', 'sale_line_id')
    def _check_total_within_line_quantity(self):
        for line in self.sale_line_id:
            total = sum(line.requested_lot_ids.mapped('quantity'))
            line_qty = line.product_uom_id._compute_quantity(
                line.product_uom_qty, line.product_id.uom_id)
            rounding = line.product_id.uom_id.rounding
            if float_compare(total, line_qty, precision_rounding=rounding) > 0:
                raise ValidationError(self.env._(
                    "The requested lot quantities (%(total)s) exceed the "
                    "line quantity (%(line_qty)s).",
                    total=total, line_qty=line_qty))
```

- [ ] **Step 4: Implement `models/sale_order_line.py`**

```python
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    requested_lot_ids = fields.One2many(
        'sale.order.line.lot', 'sale_line_id', string="Requested Lots",
        copy=True)
    lot_selection_status = fields.Selection(
        [('not_applicable', "Not Applicable"),
         ('pending', "No Lot Selected"),
         ('selected', "Lots Selected")],
        string="Lot Selection", compute='_compute_lot_selection_status')

    @api.depends('product_id.tracking', 'requested_lot_ids')
    def _compute_lot_selection_status(self):
        for line in self:
            if line.product_id.tracking != 'lot':
                line.lot_selection_status = 'not_applicable'
            elif line.requested_lot_ids:
                line.lot_selection_status = 'selected'
            else:
                line.lot_selection_status = 'pending'

    def action_open_lot_selection(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Select Lots to Deliver"),
            'res_model': 'sale.line.lot.selection',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_line_id': self.id},
        }
```

- [ ] **Step 5: Verify**

`python3 -m py_compile` on both new model files + the test file; trace the 4 tests against the constraints/compute (sum 120 > 100 → raise; foreign lot → raise; qty 0 → raise; status transitions).

- [ ] **Step 6: Commit**

```bash
git add sale_stock_lot_selection/models/sale_order_line_lot.py sale_stock_lot_selection/models/sale_order_line.py sale_stock_lot_selection/tests/
git commit -m "feat(sale_stock_lot_selection): requested-lot model, constraints and line status"
```

---

## Task 3: Reservation override on stock.move

**Files:**
- Create: `sale_stock_lot_selection/models/stock_move.py`
- Modify: `sale_stock_lot_selection/tests/test_lot_selection.py` (append 4 tests)

- [ ] **Step 1: Write the failing tests** (append to `TestLotSelection`)

```python
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
```

(The first three tests also depend on Task 4's confirm-time forcing; they are traced/executed together once Task 4 lands. `quantity_product_uom` is the move-line reserved qty expressed in product UoM — standard field.)

- [ ] **Step 2: Implement `models/stock_move.py`**

```python
from odoo import models
from odoo.tools import float_compare


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_assign(self, force_qty=False):
        if not force_qty:
            self._reserve_requested_lots()
        return super()._action_assign(force_qty=force_qty)

    def _reserve_requested_lots(self):
        """Reserve the salesperson-requested lots before the native
        reservation runs. Anything not covered here is handled by
        super()._action_assign() with the native removal strategy."""
        for move in self:
            requested_lots = move.sale_line_id.requested_lot_ids
            if not requested_lots:
                continue
            if move.picked or move.state not in ('confirmed', 'partially_available'):
                continue
            if move.move_orig_ids or move.procure_method == 'make_to_order':
                continue
            if move._should_bypass_reservation():
                continue
            if move.product_id.tracking != 'lot':
                continue
            move = move.with_company(move.company_id)
            rounding = move.product_id.uom_id.rounding
            missing = move.product_uom._compute_quantity(
                move.product_uom_qty - move.quantity,
                move.product_id.uom_id, rounding_method='HALF-UP')
            for requested in requested_lots:
                if float_compare(missing, 0, precision_rounding=rounding) <= 0:
                    break
                already_reserved = sum(
                    move.move_line_ids.filtered(
                        lambda ml, lot=requested.lot_id: ml.lot_id == lot
                    ).mapped('quantity_product_uom'))
                remaining = requested.quantity - already_reserved
                if float_compare(remaining, 0, precision_rounding=rounding) <= 0:
                    continue
                need = min(remaining, missing)
                taken = move._update_reserved_quantity(
                    need, move.location_id,
                    lot_id=requested.lot_id, strict=False)
                missing -= taken
```

Key points of the trace:
- `_update_reserved_quantity` caps at the lot's real availability and returns what it actually took, so no separate `_get_available_quantity` pre-check is needed and an exhausted lot simply contributes 0.
- After our reservations, `super()._action_assign()` recomputes each move's missing quantity from `move.quantity` (which now includes our reservations) and fills only the remainder via the native strategy, also setting the final move state (`assigned`/`partially_available`).
- The `already_reserved` subtraction makes the helper idempotent across repeated `action_assign` calls (e.g. backorders, manual "Check Availability").
- Moves without requested lots skip at the first `continue` — zero native-behavior change.

- [ ] **Step 3: Verify**

`python3 -m py_compile` on both files; trace each of the 4 tests through `_reserve_requested_lots` + the native `_action_assign` remainder logic.

- [ ] **Step 4: Commit**

```bash
git add sale_stock_lot_selection/models/stock_move.py sale_stock_lot_selection/tests/test_lot_selection.py
git commit -m "feat(sale_stock_lot_selection): reserve requested lots before native assignment"
```

---

## Task 4: Force reservation at order confirmation

**Files:**
- Create: `sale_stock_lot_selection/models/sale_order.py`

- [ ] **Step 1: Implement**

```python
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        moves = self.order_line.filtered('requested_lot_ids').move_ids.filtered(
            lambda m: m.state in ('confirmed', 'partially_available'))
        if moves:
            moves._action_assign()
        return res
```

Trace: with `reservation_method='manual'`, `super().action_confirm()` creates the delivery without reserving. Our filter picks only the moves of lines that have requested lots; `_action_assign()` runs our Task 3 override first, then the native remainder. Orders without any requested lots hit an empty recordset — untouched (this is what `test_no_selection_keeps_native_behavior` asserts).

- [ ] **Step 2: Verify**

`python3 -m py_compile sale_stock_lot_selection/models/sale_order.py`; trace the 4 Task 3 tests end-to-end (confirm → forced assign → reserved lots / fallback / no-op).

- [ ] **Step 3: Commit**

```bash
git add sale_stock_lot_selection/models/sale_order.py
git commit -m "feat(sale_stock_lot_selection): reserve requested lots immediately on order confirmation"
```

---

## Task 5: Selection wizard

**Files:**
- Create: `sale_stock_lot_selection/wizard/lot_selection_wizard.py`
- Modify: `sale_stock_lot_selection/tests/test_lot_selection.py` (append 2 tests)

- [ ] **Step 1: Write the failing tests** (append to `TestLotSelection`)

```python
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
```

- [ ] **Step 2: Implement `wizard/lot_selection_wizard.py`**

```python
from odoo import api, fields, models


class SaleLineLotSelection(models.TransientModel):
    _name = 'sale.line.lot.selection'
    _description = "Sale Line Lot Selection"

    sale_line_id = fields.Many2one(
        'sale.order.line', string="Sale Line", required=True)
    product_id = fields.Many2one(related='sale_line_id.product_id')
    line_ids = fields.One2many(
        'sale.line.lot.selection.line', 'wizard_id', string="Lots")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = res.get('sale_line_id') or self.env.context.get('default_sale_line_id')
        line = self.env['sale.order.line'].browse(line_id)
        if not line:
            return res
        warehouse = line.order_id.warehouse_id
        lots_data = self.env['stock.forecasted_product_product'].with_context(
            warehouse_id=warehouse.id)._get_lots_data(
                False, line.product_id.ids, warehouse)
        requested = {r.lot_id.id: r.quantity for r in line.requested_lot_ids}
        commands = []
        seen_lot_ids = set()
        for lot in lots_data:
            seen_lot_ids.add(lot['id'])
            commands.append((0, 0, {
                'lot_id': lot['id'],
                'available_quantity': lot['available_quantity'],
                'quantity_to_take': requested.get(lot['id'], 0.0),
            }))
        # Previously requested lots with no stock left still show, at 0 available.
        for lot_id, quantity in requested.items():
            if lot_id not in seen_lot_ids:
                commands.append((0, 0, {
                    'lot_id': lot_id,
                    'available_quantity': 0.0,
                    'quantity_to_take': quantity,
                }))
        res['line_ids'] = commands
        return res

    def action_apply(self):
        self.ensure_one()
        commands = [(5, 0, 0)]
        for wizard_line in self.line_ids:
            if wizard_line.quantity_to_take > 0:
                commands.append((0, 0, {
                    'lot_id': wizard_line.lot_id.id,
                    'quantity': wizard_line.quantity_to_take,
                }))
        self.sale_line_id.requested_lot_ids = commands
        return {'type': 'ir.actions.act_window_close'}


class SaleLineLotSelectionLine(models.TransientModel):
    _name = 'sale.line.lot.selection.line'
    _description = "Sale Line Lot Selection Line"

    wizard_id = fields.Many2one(
        'sale.line.lot.selection', required=True, ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string="Lot", required=True)
    available_quantity = fields.Float(
        string="Available", digits='Product Unit', readonly=True)
    quantity_to_take = fields.Float(
        string="Quantity to Take", digits='Product Unit')
```

- [ ] **Step 3: Verify**

`python3 -m py_compile` on the wizard + test file; trace both tests (`_get_lots_data` returns lot_b first at 30.0 — ascending —, apply writes only qty>0 rows and replaces prior content via the `(5,0,0)` command).

- [ ] **Step 4: Commit**

```bash
git add sale_stock_lot_selection/wizard/lot_selection_wizard.py sale_stock_lot_selection/tests/test_lot_selection.py
git commit -m "feat(sale_stock_lot_selection): lot selection wizard prefilled with available lots"
```

---

## Task 6: Views (button + badge on the line, wizard form)

**Files:**
- Create: `sale_stock_lot_selection/views/sale_order_views.xml`
- Create: `sale_stock_lot_selection/views/lot_selection_wizard_views.xml`

- [ ] **Step 1: `views/sale_order_views.xml`**

Adds, in the order form's line list: the status badge (yellow "No Lot Selected" / green "Lots Selected", hidden for untracked products) and the popup button (only while the order is editable — draft/sent).

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_order_form_lot_selection" model="ir.ui.view">
        <field name="name">sale.order.form.lot.selection</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='order_line']/list//field[@name='product_uom_qty']" position="after">
                <field name="lot_selection_status" optional="show" widget="badge"
                       decoration-warning="lot_selection_status == 'pending'"
                       decoration-success="lot_selection_status == 'selected'"
                       invisible="lot_selection_status == 'not_applicable'"/>
                <button name="action_open_lot_selection" type="object"
                        icon="fa-cubes" title="Select lots to deliver"
                        invisible="lot_selection_status == 'not_applicable' or parent.state not in ('draft', 'sent')"/>
            </xpath>
        </field>
    </record>
</odoo>
```

Execution note: before writing this file, fetch the actual `sale.view_order_form` arch from odoo/odoo 19.0 (`addons/sale/views/sale_order_views.xml`) and confirm the xpath target (`field[@name='order_line']/list//field[@name='product_uom_qty']`) matches; adjust the expr if the list structure differs.

- [ ] **Step 2: `views/lot_selection_wizard_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_lot_selection_wizard_form" model="ir.ui.view">
        <field name="name">sale.line.lot.selection.form</field>
        <field name="model">sale.line.lot.selection</field>
        <field name="arch" type="xml">
            <form>
                <group>
                    <field name="sale_line_id" invisible="1"/>
                    <field name="product_id" readonly="1"/>
                </group>
                <field name="line_ids">
                    <list editable="bottom" create="0" delete="0">
                        <field name="lot_id" readonly="1" force_save="1"/>
                        <field name="available_quantity" readonly="1" force_save="1"/>
                        <field name="quantity_to_take"/>
                    </list>
                </field>
                <footer>
                    <button name="action_apply" type="object" string="Apply"
                            class="btn-primary" data-hotkey="q"/>
                    <button string="Cancel" class="btn-secondary"
                            special="cancel" data-hotkey="x"/>
                </footer>
            </form>
        </field>
    </record>
</odoo>
```

- [ ] **Step 3: Verify**

Parse both files with `xml.etree.ElementTree`; confirm the manifest (Task 1) already lists both view files in `data`.

- [ ] **Step 4: Commit**

```bash
git add sale_stock_lot_selection/views/
git commit -m "feat(sale_stock_lot_selection): line badge, popup button and wizard views"
```

---

## Task 7: es_AR translations + final verification

**Files:**
- Create: `sale_stock_lot_selection/i18n/es_AR.po`

- [ ] **Step 1: Create `i18n/es_AR.po`**

Cover every user-visible string introduced by the module. Standard header (same as `stock_forecasted_lots/i18n/es_AR.po`, module name swapped), then entries — key translations:

| msgid | msgstr |
|---|---|
| Requested Lot on Sale Order Line | Lote solicitado en línea de venta |
| Requested Lots | Lotes solicitados |
| Sale Line | Línea de venta |
| Lot | Lote |
| Quantity | Cantidad |
| Quantity to take from this lot, in the product's unit of measure. | Cantidad a tomar de este lote, en la unidad de medida del producto. |
| The same lot cannot be requested twice on the same line. | El mismo lote no puede solicitarse dos veces en la misma línea. |
| Lot %(lot)s does not belong to product %(product)s. | El lote %(lot)s no pertenece al producto %(product)s. |
| The requested lot quantity must be greater than zero. | La cantidad solicitada del lote debe ser mayor a cero. |
| The requested lot quantities (%(total)s) exceed the line quantity (%(line_qty)s). | Las cantidades de lotes solicitadas (%(total)s) superan la cantidad de la línea (%(line_qty)s). |
| Lot Selection | Selección de lote |
| Not Applicable | No aplica |
| No Lot Selected | Sin lote elegido |
| Lots Selected | Lotes seleccionados |
| Select Lots to Deliver | Seleccionar lotes a entregar |
| Select lots to deliver | Seleccionar lotes a entregar |
| Sale Line Lot Selection | Selección de lotes de línea de venta |
| Sale Line Lot Selection Line | Línea de selección de lotes |
| Lots | Lotes |
| Available | Disponible |
| Quantity to Take | Cantidad a tomar |
| Apply | Aplicar |
| Cancel | Cancelar |

Each entry carries its standard `#. module:` / `#:` reference comments (`odoo-python` for code strings, `model:ir.model.fields` / `model_terms:ir.ui.view` for fields and views), following the exact format of `stock_forecasted_lots/i18n/es_AR.po`.

- [ ] **Step 2: Final structural verification**

1. `python3 -m py_compile` on every `.py` in the module.
2. ElementTree parse on every `.xml`.
3. `git ls-files sale_stock_lot_selection/` matches the planned structure exactly (no strays).
4. Manifest `data` list vs. actual files on disk.
5. Cross-check .po msgids against the actual strings in code/views.

- [ ] **Step 3: Document the manual verification checklist** (for a human on a real Odoo 19 instance)

1. Install `sale_stock_lot_selection` (pulls `stock_forecasted_lots`).
2. Run the suite: `odoo-bin -d <db> --test-enable --stop-after-init -i sale_stock_lot_selection --test-tags /sale_stock_lot_selection` — 10 tests expected green.
3. Create a lot-tracked product with two lots (100 m and 30 m). New quote, add 80 m of the product → the line shows the yellow "Sin lote elegido" badge.
4. Click the cubes button → popup lists BOBINA-B (30) first, then BOBINA-A (100). Take 30 of B. Apply → badge turns green.
5. Confirm the order → the delivery shows 30 m reserved of B and 50 m of A (fallback).
6. Repeat without selecting lots → native reservation untouched.
7. Confirm the badge/button are hidden for untracked products and the button disappears once the order is confirmed.

- [ ] **Step 4: Commit**

```bash
git add sale_stock_lot_selection/i18n/es_AR.po
git commit -m "i18n(sale_stock_lot_selection): add es_AR translations"
```
