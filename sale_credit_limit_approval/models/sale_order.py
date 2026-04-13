# sale_credit_limit_approval/models/sale_order.py
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Override de state para agregar el valor 'waiting_approval'
    # En Odoo 18 el campo state en sale.order está definido con selection_add.
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection_add=[
            ('waiting_approval', 'Esperando Aprobación'),
        ],
        ondelete={'waiting_approval': 'set default'},
    )

    # Campo informativo para mostrar en la vista el motivo del bloqueo
    credit_approval_note = fields.Char(
        string='Nota de Crédito',
        readonly=True,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Método auxiliar: comprobación de límite de crédito
    # -------------------------------------------------------------------------
    def _check_credit_limit(self):
        """
        Devuelve True si el pedido supera el límite de crédito del cliente.

        Reutiliza el campo nativo `partner_credit_warning` de Odoo, que ya
        contempla facturas impagas + órdenes de venta pendientes, evitando
        calcular manualmente una cifra diferente a la que Odoo muestra en pantalla.

        Devuelve False si el partner no tiene límite configurado (credit_limit == 0).
        """
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id

        # 0 significa sin límite: no bloqueamos
        if not partner.credit_limit:
            return False

        # `partner_credit_warning` es el campo computado nativo de Odoo 18.
        # Está vacío ('') si no hay exceso; contiene el mensaje de advertencia si sí lo hay.
        # Es la misma fuente de verdad que el warning que aparece en la orden de venta.
        return bool(self.partner_credit_warning)

    # -------------------------------------------------------------------------
    # Override de action_confirm
    # -------------------------------------------------------------------------
    def action_confirm(self):
        # Si el contexto indica que la aprobación ya fue concedida, saltear check
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

    # -------------------------------------------------------------------------
    # Acción: Aprobar crédito
    # -------------------------------------------------------------------------
    def action_approve_credit(self):
        """
        Aprueba el exceso de crédito y confirma la orden de venta.
        Solo puede ejecutarlo el supervisor_id del cliente o un admin de sistema.
        """
        self.ensure_one()
        current_user = self.env.user
        partner = self.partner_id.commercial_partner_id

        is_approver_group = self.env.ref('sale_credit_limit_approval.group_credit_limit_approver') in current_user.groups_id
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

        # Registrar aprobación en el chatter
        self.message_post(
            body=_(
                "✅ Exceso de crédito aprobado por %(user)s. La orden procede a confirmarse.",
                user=current_user.name,
            ),
            message_type='notification',
        )

        # Volver a draft y confirmar con el flag que bypasea el check de crédito
        self.write({
            'state': 'draft',
            'credit_approval_note': False,
        })
        # Usamos with_context para evitar que action_confirm vuelva a bloquear la orden
        return self.with_context(bypass_credit_limit=True).action_confirm()

    # -------------------------------------------------------------------------
    # Computed: visibilidad del botón de aprobación
    # -------------------------------------------------------------------------
    def _compute_show_approve_credit_button(self):
        approver_group = self.env.ref('sale_credit_limit_approval.group_credit_limit_approver')
        for order in self:
            if order.state != 'waiting_approval':
                order.show_approve_credit_button = False
                continue

            current_user = self.env.user
            partner = order.partner_id.commercial_partner_id
            is_approver_group = approver_group in current_user.groups_id
            is_supervisor = partner.supervisor_id and partner.supervisor_id == current_user
            order.show_approve_credit_button = bool(is_approver_group or is_supervisor)

    show_approve_credit_button = fields.Boolean(
        string='Mostrar botón de aprobación',
        compute='_compute_show_approve_credit_button',
    )

    # -------------------------------------------------------------------------
    # Cancelar una orden en waiting_approval → volver a draft
    # -------------------------------------------------------------------------
    def action_cancel(self):
        # Permitir cancelar órdenes bloqueadas sin error de flujo
        waiting = self.filtered(lambda o: o.state == 'waiting_approval')
        if waiting:
            waiting.write({'state': 'cancel', 'credit_approval_note': False})
        remaining = self - waiting
        if remaining:
            return super(SaleOrder, remaining).action_cancel()
        return True
