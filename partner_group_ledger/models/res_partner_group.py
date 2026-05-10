from odoo import models, fields

class ResPartnerGroup(models.Model):
    _name = 'res.partner.group'
    _description = 'Partner Group'

    name = fields.Char(string='Group Name', required=True)
    partner_ids = fields.One2many('res.partner', 'partner_group_id', string='Partners')
