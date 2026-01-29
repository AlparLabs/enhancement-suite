from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # This field stores the link back to the PIM
    pim_id = fields.Many2one('pim', string='Origin PIM', readonly=True)