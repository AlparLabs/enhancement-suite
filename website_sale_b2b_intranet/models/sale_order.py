# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    claim_ids = fields.One2many(
        'b2b.order.claim',
        'order_id',
        string='Reclamos B2B',
    )
    claim_count = fields.Integer(
        string='Cantidad de Reclamos',
        compute='_compute_claim_count',
    )

    @api.depends('claim_ids')
    def _compute_claim_count(self):
        for order in self:
            order.claim_count = len(order.claim_ids)

    def action_view_claims(self):
        self.ensure_one()
        action = self.env.ref('website_sale_b2b_intranet.action_b2b_order_claim').read()[0]
        action['domain'] = [('order_id', '=', self.id)]
        action['context'] = {'default_order_id': self.id}
        return action
