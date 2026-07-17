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
