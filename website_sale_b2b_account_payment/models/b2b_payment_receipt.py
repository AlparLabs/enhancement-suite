# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class B2BPaymentReceipt(models.Model):
    _name = 'b2b.payment.receipt'
    _description = 'Rendición de Comprobante de Transferencia Bancaria B2B'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string="Referencia",
        default='/',
        readonly=True,
        copy=False
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Cliente / Franquiciado",
        required=True,
        index=True,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string="Compañía",
        default=lambda self: self.env.company,
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    amount = fields.Monetary(
        string="Monto Informado",
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    date = fields.Date(
        string="Fecha de Transferencia",
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    operation_number = fields.Char(
        string="N° de Transacción / Operación",
        required=True,
        help="Número de referencia o comprobante emitido por el banco o billetera.",
        tracking=True
    )
    bank_origin = fields.Char(
        string="Banco de Origen / Cuenta",
        help="Entidad bancaria o billetera desde la que se transfirió (ej. Santander, Galicia, Mercado Pago)."
    )
    notes = fields.Text(
        string="Observaciones del Cliente"
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'b2b_payment_receipt_ir_attachment_rel',
        'receipt_id',
        'attachment_id',
        string="Comprobante Adjunto"
    )
    invoice_ids = fields.Many2many(
        'account.move',
        'b2b_payment_receipt_account_move_rel',
        'receipt_id',
        'move_id',
        string="Facturas Imputadas",
        domain="[('partner_id.commercial_partner_id', '=', partner_id), ('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]"
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Pendiente de Verificación'),
            ('verified', 'Verificado y Acreditado'),
            ('rejected', 'Rechazado'),
        ],
        string="Estado",
        default='draft',
        required=True,
        tracking=True
    )
    rejection_reason = fields.Text(
        string="Motivo de Rechazo",
        copy=False
    )
    verified_by = fields.Many2one(
        'res.users',
        string="Verificado por",
        readonly=True,
        copy=False
    )
    verified_date = fields.Datetime(
        string="Fecha de Verificación",
        readonly=True,
        copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                today = fields.Date.context_today(self)
                vals['name'] = f"TRF-{today.strftime('%Y%m')}-{self.env['ir.sequence'].next_by_code('b2b.payment.receipt') or 'NEW'}"
        records = super().create(vals_list)
        for record in records:
            if record.name.endswith('NEW'):
                record.name = f"TRF-{record.date.strftime('%Y%m')}-{record.id:04d}"
            record._schedule_treasury_activity()
        return records

    def _schedule_treasury_activity(self):
        """
        Crea una actividad automática para el área de Administración / Tesorería al recibirse un comprobante.
        """
        self.ensure_one()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return

        # Buscar usuarios del grupo contable en la compañía
        account_group = self.env.ref('account.group_account_invoice', raise_if_not_found=False)
        accountant = False
        if account_group:
            accountant = self.env['res.users'].search([
                ('company_ids', 'in', self.company_id.id),
                ('groups_id', 'in', account_group.id)
            ], limit=1)
        user_id = accountant.id if accountant else (self.env.user.id or self.env.ref('base.user_admin').id)

        self.activity_schedule(
            activity_type_id=activity_type.id,
            user_id=user_id,
            summary=_(
                "Transferencia recibida de %(partner)s por %(amount)s %(currency)s",
                partner=self.partner_id.name,
                amount=self.amount,
                currency=self.currency_id.symbol or self.currency_id.name
            ),
            note=_(
                "Comprobante N° %(ref)s informado el %(date)s.<br/>"
                "Banco: %(bank)s.<br/>"
                "Verifique la acreditación en extracto bancario para conciliar el saldo.",
                ref=self.operation_number,
                date=self.date,
                bank=self.bank_origin or "No especificado"
            )
        )

    def action_verify(self):
        self.ensure_one()
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
        })
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reject(self, reason=None):
        self.ensure_one()
        vals = {
            'state': 'rejected',
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
        }
        if reason:
            vals['rejection_reason'] = reason
        self.write(vals)
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_set_to_draft(self):
        self.write({'state': 'draft'})
