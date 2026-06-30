from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    channel_id = fields.Many2one(
        comodel_name='res.partner.channel',
        string='Channel',
        compute='_compute_channel',
        store=True,
        readonly=False,
        precompute=True,
        help="Channel for this order. Auto-filled from the customer, editable.",
    )
    channel_detail_ids = fields.Many2many(
        comodel_name='res.partner.channel.detail',
        relation='sale_order_channel_detail_rel',
        column1='order_id',
        column2='detail_id',
        string='Channel Details',
        compute='_compute_channel',
        store=True,
        readonly=False,
        precompute=True,
        domain="[('channel_id', '=', channel_id)]",
        help="Channel details for this order. Auto-filled from the customer, editable.",
    )

    @api.depends('partner_id')
    def _compute_channel(self):
        for order in self:
            order.channel_id = order.partner_id.channel_id
            order.channel_detail_ids = order.partner_id.channel_detail_ids

    @api.onchange('channel_id')
    def _onchange_channel_id(self):
        # Drop details that no longer match the selected channel.
        self.channel_detail_ids = self.channel_detail_ids.filtered(
            lambda d: d.channel_id == self.channel_id
        )
