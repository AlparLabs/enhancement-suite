from datetime import timedelta
from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_b2b_financial_status(self, website=None):
        """
        Evalúa el estado financiero del cliente delegando en su contacto comercial.
        """
        self.ensure_one()
        current_website = website or self.website_id or self.env['website'].get_current_website()
        return self.partner_id.commercial_partner_id._get_b2b_financial_status(
            current_website, order_amount=self.amount_total
        )

    def _cart_add(self, product_id: int, quantity: float = 1.0, *, uom_id: int | None = None, **kwargs) -> dict:
        """
        Impide agregar productos al carrito si el contacto comercial tiene bloqueo financiero activo.
        """
        self.ensure_one()
        current_website = self.website_id or self.env['website'].get_current_website()
        status = self.partner_id.commercial_partner_id._get_b2b_financial_status(current_website)
        if status.get('is_blocked'):
            raise UserError(_(
                "Tu cuenta presenta comprobantes vencidos o margen de crédito superado. "
                "La toma de pedidos se encuentra suspendida hasta regularizar los saldos pendientes."
            ))
        return super()._cart_add(product_id=product_id, quantity=quantity, uom_id=uom_id, **kwargs)

    def _cart_update_line_quantity(self, line_id, quantity, **kwargs):
        """
        Impide modificar o reanudar cantidades en el carrito si el contacto tiene bloqueo financiero.
        """
        self.ensure_one()
        current_website = self.website_id or self.env['website'].get_current_website()
        status = self.partner_id.commercial_partner_id._get_b2b_financial_status(current_website)
        if status.get('is_blocked'):
            raise UserError(_(
                "Tu cuenta presenta comprobantes vencidos o margen de crédito superado. "
                "La toma de pedidos se encuentra suspendida hasta regularizar los saldos pendientes."
            ))
        return super()._cart_update_line_quantity(line_id, quantity, **kwargs)


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
