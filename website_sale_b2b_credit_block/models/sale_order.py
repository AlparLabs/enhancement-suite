from datetime import timedelta
from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_b2b_financial_status(self, website=None):
        """
        Evalúa el estado financiero del cliente (commercial_partner_id) para determinar
        si sus compras en cuenta corriente deben ser bloqueadas.

        Criterios:
        1. Facturas vencidas impagas con fecha de vencimiento anterior a (hoy - días de gracia).
        2. Exceso de límite de crédito evaluando ÚNICAMENTE:
           Deuda Facturada (partner.credit) + Total del Pedido Actual > partner.credit_limit.
        """
        self.ensure_one()
        current_website = website or self.website_id or self.env['website'].get_current_website()

        if not current_website or not current_website.b2b_credit_block_active:
            return {
                'is_blocked': False,
                'has_overdue': False,
                'overdue_amount': 0.0,
                'invoiced_debt': 0.0,
                'credit_limit': 0.0,
                'order_amount': self.amount_total,
                'exceeds_limit': False,
                'excess_amount': 0.0,
                'grace_days': 0,
            }

        partner = self.partner_id.commercial_partner_id
        today = fields.Date.context_today(self)

        # 1. Resolución de días de gracia
        grace_days = (
            partner.b2b_grace_period_override
            if partner.b2b_grace_period_override >= 0
            else current_website.b2b_grace_period_days
        )
        cutoff_date = today - timedelta(days=grace_days)

        # 2. Facturas vencidas impagas
        overdue_moves = self.env['account.move'].search([
            ('partner_id', 'child_of', partner.id),
            ('move_type', 'in', ('out_invoice', 'out_receipt')),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('in_payment', 'paid', 'reversed')),
            ('invoice_date_due', '<', cutoff_date),
        ])
        has_overdue = bool(overdue_moves)
        overdue_amount = sum(overdue_moves.mapped('amount_residual'))

        # 3. Límite de crédito (estrictamente saldo contable facturado)
        invoiced_debt = partner.credit
        credit_limit = partner.credit_limit
        order_amount = self.amount_total

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

    def action_confirm(self):
        """
        Bloquea la confirmación en backend si el cliente tiene bloqueo financiero activo,
        enlazando con el estado 'waiting_approval' si está disponible.
        """
        if self.env.context.get('bypass_credit_limit'):
            return super().action_confirm()

        blocked_orders = self.env['sale.order']
        to_confirm_orders = self.env['sale.order']

        for order in self.filtered(lambda o: o.state in ('draft', 'sent')):
            website = order.website_id or self.env['website'].get_current_website()
            status = order._get_b2b_financial_status(website)

            if status['is_blocked']:
                partner = order.partner_id.commercial_partner_id
                reasons = []
                if status['has_overdue']:
                    reasons.append(
                        _("Facturas vencidas impagas por: %s", status['overdue_amount'])
                    )
                if status['exceeds_limit']:
                    reasons.append(
                        _("Límite de crédito excedido (Límite: %s | Deuda facturada: %s | Total orden: %s | Exceso: %s)",
                          status['credit_limit'], status['invoiced_debt'], status['order_amount'], status['excess_amount'])
                    )

                msg = _("⚠️ Orden bloqueada por política financiera B2B:\n- ") + "\n- ".join(reasons)

                # Si el estado 'waiting_approval' existe (por ejemplo proveniente de sale_credit_limit_approval)
                has_waiting_approval = 'waiting_approval' in dict(self._fields['state']._description_selection(self.env))
                if has_waiting_approval:
                    order.write({
                        'state': 'waiting_approval',
                        'credit_approval_note': msg,
                    })
                    order.message_post(body=msg, message_type='notification')
                    blocked_orders |= order
                else:
                    raise UserError(msg)
            else:
                to_confirm_orders |= order

        if to_confirm_orders:
            return super(SaleOrder, to_confirm_orders).action_confirm()
        return True
