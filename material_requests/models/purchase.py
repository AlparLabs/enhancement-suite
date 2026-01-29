from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # The link back to the Project Request
    pim_id = fields.Many2one('pim', string='Origin PIM', readonly=True)
    sim_id = fields.Many2one('sim', string='Origin SIM', readonly=True)