from odoo import fields, models


class ResPartnerChannel(models.Model):
    _name = 'res.partner.channel'
    _description = 'Partner Channel'
    _order = 'sequence, name'

    name = fields.Char(string='Channel', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    detail_ids = fields.One2many(
        comodel_name='res.partner.channel.detail',
        inverse_name='channel_id',
        string='Channel Details',
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The channel name must be unique.'),
    ]
