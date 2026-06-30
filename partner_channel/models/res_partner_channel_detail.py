from odoo import api, fields, models


class ResPartnerChannelDetail(models.Model):
    _name = 'res.partner.channel.detail'
    _description = 'Partner Channel Detail'
    _order = 'channel_id, name'

    name = fields.Char(string='Channel Detail', required=True, translate=True)
    channel_id = fields.Many2one(
        comodel_name='res.partner.channel',
        string='Channel',
        required=True,
        ondelete='cascade',
    )
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_channel_uniq', 'unique(channel_id, name)',
         'The detail name must be unique within its channel.'),
    ]

    @api.depends('name', 'channel_id.name')
    def _compute_display_name(self):
        for detail in self:
            if detail.channel_id:
                detail.display_name = f'{detail.channel_id.name} / {detail.name}'
            else:
                detail.display_name = detail.name
