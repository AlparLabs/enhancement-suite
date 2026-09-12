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

    def _get_b2b_financial_status(self, website=None, order_amount=0.0):
        """
        Evalúa el estado financiero del contacto comercial para determinar si
        sus compras en cuenta corriente / B2B deben ser bloqueadas.
        """
        self.ensure_one()
        current_website = website or self.env['website'].get_current_website()

        if not current_website or not current_website.b2b_credit_block_active:
            return {
                'is_blocked': False,
                'has_overdue': False,
                'overdue_amount': 0.0,
                'invoiced_debt': 0.0,
                'credit_limit': 0.0,
                'order_amount': order_amount,
                'exceeds_limit': False,
                'excess_amount': 0.0,
                'grace_days': 0,
            }

        commercial_partner = self.commercial_partner_id
        today = fields.Date.context_today(self)

        # 1. Resolución de días de gracia
        from datetime import timedelta
        grace_days = (
            commercial_partner.b2b_grace_period_override
            if commercial_partner.b2b_grace_period_override >= 0
            else current_website.b2b_grace_period_days
        )
        cutoff_date = today - timedelta(days=grace_days)

        # 2. Facturas vencidas impagas
        overdue_moves = self.env['account.move'].search([
            ('partner_id', 'child_of', commercial_partner.id),
            ('move_type', 'in', ('out_invoice', 'out_receipt')),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('in_payment', 'paid', 'reversed')),
            ('invoice_date_due', '<', cutoff_date),
        ])
        has_overdue = bool(overdue_moves)
        overdue_amount = sum(overdue_moves.mapped('amount_residual'))

        # 3. Límite de crédito (estrictamente saldo contable facturado)
        invoiced_debt = commercial_partner.credit
        credit_limit = commercial_partner.credit_limit

        exceeds_limit = False
        excess_amount = 0.0
        if credit_limit > 0:
            total_exposure = invoiced_debt + order_amount
            if total_exposure > credit_limit:
                exceeds_limit = True
                excess_amount = total_exposure - credit_limit

        return {
            'is_blocked': has_overdue or exceeds_limit,
            'has_overdue': has_overdue,
            'overdue_amount': overdue_amount,
            'invoiced_debt': invoiced_debt,
            'credit_limit': credit_limit,
            'order_amount': order_amount,
            'exceeds_limit': exceeds_limit,
            'excess_amount': excess_amount,
            'grace_days': grace_days,
            'cutoff_date': cutoff_date,
        }

