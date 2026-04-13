# sale_credit_limit_approval/models/res_partner.py
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # credit_limit es un campo nativo de Odoo (account module).
    # Solo nos aseguramos de que esté disponible; no lo redefinimos.

    supervisor_id = fields.Many2one(
        comodel_name='res.users',
        string='Supervisor de Crédito',
        help='Usuario responsable de autorizar excesos en el límite de crédito de este cliente.',
        tracking=True,
    )
