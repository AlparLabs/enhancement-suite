from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    partner_group_id = fields.Many2one(
        'res.partner.group', 
        related='partner_id.partner_group_id', 
        store=True, 
        string='Partner Group'
    )
