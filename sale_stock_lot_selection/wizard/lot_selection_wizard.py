from odoo import api, fields, models


class SaleLineLotSelection(models.TransientModel):
    _name = 'sale.line.lot.selection'
    _description = "Sale Line Lot Selection"

    sale_line_id = fields.Many2one(
        'sale.order.line', string="Sale Line", required=True)
    product_id = fields.Many2one(related='sale_line_id.product_id')
    line_ids = fields.One2many(
        'sale.line.lot.selection.line', 'wizard_id', string="Lots")
    line_quantity = fields.Float(
        string="Quantity to Sell", digits='Product Unit',
        compute='_compute_quantities',
        help="Quantity being sold on the line, in the product's unit of measure.")
    remaining_quantity = fields.Float(
        string="Left to Assign", digits='Product Unit',
        compute='_compute_quantities',
        help="Line quantity not yet covered by the selected lots. "
             "It will be reserved with Odoo's automatic strategy.")

    @api.depends('sale_line_id', 'line_ids.quantity_to_take')
    def _compute_quantities(self):
        for wizard in self:
            line = wizard.sale_line_id
            line_qty = 0.0
            if line:
                line_qty = line.product_uom_id._compute_quantity(
                    line.product_uom_qty, line.product_id.uom_id)
            wizard.line_quantity = line_qty
            wizard.remaining_quantity = line_qty - sum(
                wizard.line_ids.mapped('quantity_to_take'))

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
