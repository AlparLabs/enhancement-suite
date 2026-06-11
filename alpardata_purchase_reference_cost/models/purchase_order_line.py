from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    reference_cost = fields.Float(
        string='Costo de referencia',
        related='product_id.reference_cost',
        digits='Product Price',
        readonly=True,
        store=False,
    )
