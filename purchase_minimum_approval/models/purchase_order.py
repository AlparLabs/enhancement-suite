# purchase_minimum_approval/models/purchase_order.py
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(
        selection_add=[
            ('waiting_approval', 'Esperando Aprobación'),
        ],
        ondelete={'waiting_approval': 'set default'},
    )

    minimum_approval_note = fields.Char(
        string='Nota de Mínimo de Compra',
        readonly=True,
        copy=False,
    )

    purchase_minimum_warning = fields.Char(
        string='Advertencia de mínimo de compra',
        compute='_compute_purchase_minimum_warning',
    )

    show_approve_minimum_button = fields.Boolean(
        string='Mostrar botón de aprobación de mínimo',
        compute='_compute_show_approve_minimum_button',
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_minimum_partner(self):
        self.ensure_one()
        return self.partner_id.commercial_partner_id

    def _amount_untaxed_company_currency(self):
        """Subtotal de la orden convertido a la moneda de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        order_currency = self.currency_id or company.currency_id
        return order_currency._convert(
            self.amount_untaxed,
            company.currency_id,
            company,
            self.date_order or fields.Date.context_today(self),
        )

    def _check_purchase_minimum(self):
        """True si la orden queda por debajo del mínimo del proveedor."""
        self.ensure_one()
        partner = self._get_minimum_partner()
        if not partner.apply_purchase_minimum or partner.purchase_minimum_amount <= 0:
            return False
        company_currency = (self.company_id or self.env.company).currency_id
        subtotal = self._amount_untaxed_company_currency()
        # subtotal < minimo  ->  -1
        return float_compare(
            subtotal,
            partner.purchase_minimum_amount,
            precision_rounding=company_currency.rounding,
        ) < 0

    # -------------------------------------------------------------------------
    # Confirmación
    # -------------------------------------------------------------------------
    def button_confirm(self):
        if self.env.context.get('bypass_purchase_minimum'):
            return super().button_confirm()

        to_confirm = self.env['purchase.order']

        for order in self:
            if order.state not in ('draft', 'sent'):
                to_confirm |= order
                continue
            if order._check_purchase_minimum():
                partner = order._get_minimum_partner()
                company_currency = (order.company_id or self.env.company).currency_id
                minimum = partner.purchase_minimum_amount
                subtotal = order._amount_untaxed_company_currency()
                note = _(
                    "Requiere aprobación. Mínimo: %(min)s %(cur)s | "
                    "Subtotal orden: %(sub)s %(cur)s",
                    min=minimum,
                    sub=round(subtotal, 2),
                    cur=company_currency.name,
                )
                order.write({
                    'state': 'waiting_approval',
                    'minimum_approval_note': note,
                })
                order.message_post(
                    body=_(
                        "⚠️ Orden bloqueada: no alcanza el mínimo de compra del "
                        "proveedor.\n%(note)s",
                        note=note,
                    ),
                    message_type='notification',
                )
            else:
                to_confirm |= order

        if to_confirm:
            return super(PurchaseOrder, to_confirm).button_confirm()
        return True

    # -------------------------------------------------------------------------
    # Aprobación
    # -------------------------------------------------------------------------
    def action_approve_minimum(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'purchase_minimum_approval.group_purchase_minimum_approver'
        ):
            raise AccessError(_(
                "No tiene permiso para aprobar el mínimo de compra. "
                "Se requiere pertenecer al grupo aprobador de compras."
            ))
        if self.state != 'waiting_approval':
            raise UserError(_("Esta orden no está pendiente de aprobación de mínimo."))

        self.message_post(
            body=_(
                "✅ Mínimo de compra aprobado por %(user)s. La orden procede a confirmarse.",
                user=self.env.user.name,
            ),
            message_type='notification',
        )
        self.write({'state': 'draft', 'minimum_approval_note': False})
        return self.with_context(bypass_purchase_minimum=True).button_confirm()

    # -------------------------------------------------------------------------
    # Cancelación
    # -------------------------------------------------------------------------
    def button_cancel(self):
        waiting = self.filtered(lambda o: o.state == 'waiting_approval')
        if waiting:
            waiting.write({'state': 'cancel', 'minimum_approval_note': False})
        remaining = self - waiting
        if remaining:
            return super(PurchaseOrder, remaining).button_cancel()
        return True

    # -------------------------------------------------------------------------
    # Campos computados de UI
    # -------------------------------------------------------------------------
    @api.depends(
        'state', 'amount_untaxed', 'currency_id',
        'partner_id.commercial_partner_id.apply_purchase_minimum',
        'partner_id.commercial_partner_id.purchase_minimum_amount',
    )
    def _compute_purchase_minimum_warning(self):
        for order in self:
            warning = ''
            if order.state in ('draft', 'sent') and order._check_purchase_minimum():
                partner = order._get_minimum_partner()
                company_currency = (order.company_id or self.env.company).currency_id
                warning = _(
                    "Este proveedor exige un mínimo de compra de %(min)s %(cur)s "
                    "(subtotal actual: %(sub)s %(cur)s). Al confirmar, la orden "
                    "quedará pendiente de aprobación.",
                    min=partner.purchase_minimum_amount,
                    sub=round(order._amount_untaxed_company_currency(), 2),
                    cur=company_currency.name,
                )
            order.purchase_minimum_warning = warning

    @api.depends('state')
    def _compute_show_approve_minimum_button(self):
        is_approver = self.env.user.has_group(
            'purchase_minimum_approval.group_purchase_minimum_approver'
        )
        for order in self:
            order.show_approve_minimum_button = bool(
                order.state == 'waiting_approval' and is_approver
            )
