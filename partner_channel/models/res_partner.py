from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    channel_id = fields.Many2one(
        comodel_name='res.partner.channel',
        string='Channel',
        help="Commercial channel this contact belongs to.",
    )
    channel_detail_ids = fields.Many2many(
        comodel_name='res.partner.channel.detail',
        relation='res_partner_channel_detail_rel',
        column1='partner_id',
        column2='detail_id',
        string='Channel Details',
        domain="[('channel_id', '=', channel_id)]",
        help="Details of the channel this contact belongs to. "
             "A contact may belong to several details of the same channel.",
    )

    @api.onchange('channel_id')
    def _onchange_channel_id(self):
        # Drop details that no longer match the selected channel.
        self.channel_detail_ids = self.channel_detail_ids.filtered(
            lambda d: d.channel_id == self.channel_id
        )
