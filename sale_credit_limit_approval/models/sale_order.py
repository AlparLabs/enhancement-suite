from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection_add=[
            ('waiting_approval', 'Esperando Aprobación'),
        ],
        ondelete={'waiting_approval': 'set default'},
    )

    credit_approval_note = fields.Char(
        string='Nota de Crédito',
        readonly=True,
        copy=False,
    )

    show_approve_credit_button = fields.Boolean(
        string='Mostrar botón de aprobación',
        compute='_compute_show_approve_credit_button',
    )

    def _check_credit_limit(self) -> bool:
        """
        Devuelve True si el pedido supera el límite de crédito del cliente.

        Reutiliza el campo nativo `partner_credit_warning` de Odoo, que ya
        contempla facturas impagas + órdenes de venta pendientes, evitando
        calcular manualmente una cifra diferente a la que Odoo muestra en pantalla.

        Devuelve False si el partner no tiene límite configurado (credit_limit == 0).
        """
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id

        if not partner.credit_limit:
            return False

        return bool(self.partner_credit_warning)

    def action_confirm(self) -> bool:
        if self.env.context.get('bypass_credit_limit'):
            return super().action_confirm()

        blocked = self.env['sale.order']
        to_confirm = self.env['sale.order']

        for order in self.filtered(lambda o: o.state in ('draft', 'sent')):
            if order._check_credit_limit():
                partner = order.partner_id.commercial_partner_id
                current_credit = partner.credit
                credit_limit = partner.credit_limit

                msg = _(
                    "⚠️ Orden bloqueada por límite de crédito.\n"
                    "Límite: %(limit)s | Saldo actual: %(credit)s | "
                    "Total orden: %(total)s\n"
                    "Se requiere aprobación del supervisor: %(supervisor)s",
                    limit=credit_limit,
                    credit=current_credit,
                    total=order.amount_total,
                    supervisor=partner.supervisor_id.name if partner.supervisor_id else _('Sin asignar'),
                )
                order.write({
                    'state': 'waiting_approval',
                    'credit_approval_note': _(
                        "Requiere aprobación. Límite: %s | Crédito usado: %s | Total orden: %s"
                    ) % (credit_limit, current_credit, order.amount_total),
                })
                order.message_post(body=msg, message_type='notification')
                blocked |= order
            else:
                to_confirm |= order

        if to_confirm:
            return super(SaleOrder, to_confirm).action_confirm()
        return True

    def action_approve_credit(self) -> bool:
        """
        Aprueba el exceso de crédito y confirma la orden de venta.
        Solo puede ejecutarlo el supervisor_id del cliente o un miembro del grupo aprobador.
        """
        self.ensure_one()
        current_user = self.env.user
        partner = self.partner_id.commercial_partner_id

        is_approver_group = current_user.has_group('sale_credit_limit_approval.group_credit_limit_approver')
        is_supervisor = partner.supervisor_id and partner.supervisor_id == current_user

        if not (is_approver_group or is_supervisor):
            raise AccessError(
                _(
                    "No tiene permiso para aprobar este exceso de crédito. "
                    "Solo el supervisor '%s' o un administrador del sistema puede hacerlo.",
                    partner.supervisor_id.name if partner.supervisor_id else _('Sin asignar'),
                )
            )

        if self.state != 'waiting_approval':
            raise UserError(_("Esta orden no está pendiente de aprobación de crédito."))

        self._do_approve_credit(current_user)
        return self.with_context(bypass_credit_limit=True).action_confirm()

    def action_open_pin_dialog(self) -> dict:
        """Abre el wizard de aprobación por PIN como diálogo modal nativo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Aprobación por PIN de Crédito'),
            'res_model': 'sale.credit.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_approve_credit_by_pin(self, pin) -> bool:
        """
        Permite que un aprobador autorice la orden ingresando su PIN de empleado,
        sin necesidad de que el usuario actual sea del grupo aprobador.
        """
        self.ensure_one()

        if not pin:
            raise UserError(_("Debe ingresar un PIN."))

        if self.state != 'waiting_approval':
            raise UserError(_("Esta orden no está pendiente de aprobación de crédito."))

        partner = self.partner_id.commercial_partner_id
        approver_group = self.env.ref('sale_credit_limit_approval.group_credit_limit_approver')
        approver_user_ids = approver_group.user_ids.ids

        if partner.supervisor_id:
            approver_user_ids = list(set(approver_user_ids + [partner.supervisor_id.id]))

        employee = self.env['hr.employee'].sudo().search([
            ('pin', '=', pin),
            ('user_id', 'in', approver_user_ids),
        ], limit=1)

        if not employee:
            raise UserError(_(
                "PIN incorrecto o el empleado no tiene permisos para aprobar límites de crédito."
            ))

        self._do_approve_credit(employee.user_id, via_pin=True)
        return self.with_context(bypass_credit_limit=True).action_confirm()

    def _do_approve_credit(self, approver_user, via_pin=False) -> None:
        """Registra la aprobación en el chatter y resetea el estado a draft."""
        suffix = _(" (vía PIN)") if via_pin else ""
        self.message_post(
            body=_(
                "✅ Exceso de crédito aprobado por %(user)s%(suffix)s. La orden procede a confirmarse.",
                user=approver_user.name,
                suffix=suffix,
            ),
            message_type='notification',
        )
        self.write({
            'state': 'draft',
            'credit_approval_note': False,
        })

    @api.depends('state', 'partner_id')
    def _compute_show_approve_credit_button(self) -> None:
        for order in self:
            if order.state != 'waiting_approval':
                order.show_approve_credit_button = False
                continue

            current_user = self.env.user
            partner = order.partner_id.commercial_partner_id
            is_approver_group = current_user.has_group('sale_credit_limit_approval.group_credit_limit_approver')
            is_supervisor = partner.supervisor_id and partner.supervisor_id == current_user
            order.show_approve_credit_button = bool(is_approver_group or is_supervisor)

    def action_cancel(self) -> bool:
        waiting = self.filtered(lambda o: o.state == 'waiting_approval')
        if waiting:
            waiting.write({'state': 'cancel', 'credit_approval_note': False})
        remaining = self - waiting
        if remaining:
            return super(SaleOrder, remaining).action_cancel()
        return True
