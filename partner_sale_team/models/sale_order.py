from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # In Odoo 19, team_id is a computed field. We extend its depends
    # to include partner preferred_team_id and give it priority.
    @api.depends('user_id', 'partner_id.preferred_team_id')
    def _compute_team_id(self):
        orders_with_team = self.filtered(lambda o: o.partner_id.preferred_team_id)
        for order in orders_with_team:
            order.team_id = order.partner_id.preferred_team_id
        super(SaleOrder, self - orders_with_team)._compute_team_id()
