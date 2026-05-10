from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_group_id = fields.Many2one('res.partner.group', string='Partner Group', help="Group that this partner belongs to for consolidated reporting.")
