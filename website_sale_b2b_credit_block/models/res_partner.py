from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    b2b_website_ids = fields.Many2many(
        comodel_name='website',
        relation='res_partner_website_b2b_rel',
        column1='partner_id',
        column2='website_id',
        string="Canales web autorizados",
        help="Sitios web en los que este contacto tiene autorización para comprar.",
    )
    b2b_grace_period_override = fields.Integer(
        string="Días de gracia personalizados",
        default=-1,
        help="Si es >= 0, reemplaza los días de gracia predeterminados del sitio web para este cliente.",
    )

    def get_base_url(self):
        """
        Sobreescribe la URL base del contacto para que las invitaciones de portal
        (portal.wizard) utilicen el dominio del canal asignado al cliente.
        """
        if len(self) == 1 and self.b2b_website_ids:
            return self.b2b_website_ids[0].get_base_url()
        return super().get_base_url()
