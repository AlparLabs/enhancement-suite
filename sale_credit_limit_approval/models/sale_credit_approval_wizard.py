# sale_credit_limit_approval/models/sale_credit_approval_wizard.py
from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleCreditApprovalWizard(models.TransientModel):
    _name = 'sale.credit.approval.wizard'
    _description = 'Aprobación de crédito por PIN de empleado'

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Orden de Venta',
        required=True,
        readonly=True,
    )
    # Mostramos el cliente y el monto para contexto visual del aprobador
    partner_id = fields.Many2one(
        related='order_id.partner_id',
        string='Cliente',
        readonly=True,
    )
    amount_total = fields.Monetary(
        related='order_id.amount_total',
        string='Total de la Orden',
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id',
        readonly=True,
    )
    credit_approval_note = fields.Char(
        related='order_id.credit_approval_note',
        string='Motivo de bloqueo',
        readonly=True,
    )
    pin = fields.Char(
        string='PIN del Aprobador',
        required=True,
    )

    def action_confirm_pin(self):
        """Valida el PIN y aprueba la orden. Cierra el wizard si tiene éxito."""
        self.ensure_one()
        if not self.pin:
            raise UserError(_("Debe ingresar el PIN."))
        # Delegar toda la lógica de validación al método del sale.order
        self.order_id.action_approve_credit_by_pin(self.pin)
        # Cerrar el wizard
        return {'type': 'ir.actions.act_window_close'}
