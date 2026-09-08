from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    b2b_credit_block_active = fields.Boolean(
        string="Activar bloqueo financiero B2B",
        default=True,
        help="Habilita el control de facturas vencidas y límite de crédito en el checkout web.",
    )
    b2b_grace_period_days = fields.Integer(
        string="Días de gracia para facturas vencidas",
        default=0,
        help="Días de tolerancia tras el vencimiento de una factura antes de bloquear compras.",
    )

    def has_ecommerce_access(self):
        """
        Sobreescribe el acceso a eCommerce para validar los canales autorizados
        del partner, permitiendo siempre el acceso a usuarios internos y evitando
        bloquear a usuarios públicos antes del login.
        """
        self.ensure_one()
        user = self.env.user

        # 1. Usuarios internos (empleados/admin) siempre tienen acceso a previsualizar la tienda
        if user._is_internal():
            return True

        # 2. Usuarios públicos siguen el comportamiento nativo
        if user._is_public():
            return super().has_ecommerce_access()

        # 3. Si nativamente ya no tiene acceso, respetarlo
        if not super().has_ecommerce_access():
            return False

        # 4. Validar canales web asignados al partner del usuario portal
        partner = user.partner_id
        if partner.b2b_website_ids and self not in partner.b2b_website_ids:
            return False

        return True
