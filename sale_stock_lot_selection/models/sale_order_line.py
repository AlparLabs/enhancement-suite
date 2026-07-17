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
