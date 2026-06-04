from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    preferred_team_id = fields.Many2one(
        comodel_name='crm.team',
        string='Equipo de ventas',
        help="Equipo de ventas que se usará por defecto para este cliente.",
    )
