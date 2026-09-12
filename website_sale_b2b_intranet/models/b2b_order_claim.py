# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class B2BOrderClaim(models.Model):
    _name = 'b2b.order.claim'
    _description = 'Reclamo de Calidad y Entrega B2B'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Código de Reclamo',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    order_id = fields.Many2one(
        'sale.order',
        string='Pedido de Venta',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        related='order_id.partner_id',
        store=True,
        readonly=True,
    )
    commercial_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente / Franquiciado',
        related='order_id.partner_id.commercial_partner_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='order_id.company_id',
        store=True,
        readonly=True,
    )
    date = fields.Datetime(
        string='Fecha de Ingreso',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    claim_type = fields.Selection([
        ('missing', 'Faltante de mercadería (unidades o bultos no recibidos)'),
        ('damaged', 'Mercadería dañada en tránsito (roturas, abolladuras)'),
        ('quality', 'Desviación de calidad o defecto de empaque'),
        ('other', 'Otro inconveniente'),
    ], string='Tipo de Inconveniente', required=True, default='missing', tracking=True)

    product_id = fields.Many2one(
        'product.product',
        string='Producto / Variedad Afectada',
        tracking=True,
    )
    affected_qty = fields.Float(
        string='Cantidad Afectada',
        default=0.0,
        tracking=True,
    )
    lot_number = fields.Char(
        string='N° de Lote / Vencimiento',
        tracking=True,
    )
    description = fields.Text(
        string='Descripción Detallada',
        required=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'b2b_order_claim_ir_attachment_rel',
        'claim_id',
        'attachment_id',
        string='Evidencia Fotográfica y Documentación',
    )
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('in_progress', 'En Análisis'),
        ('resolved', 'Resuelto'),
        ('rejected', 'Desestimado'),
    ], string='Estado', default='draft', tracking=True, required=True)

    resolution_type = fields.Selection([
        ('credit_note', 'Emisión de Nota de Crédito'),
        ('replacement', 'Reposición en Próximo Pedido'),
        ('none', 'Sin Compensación Económica'),
    ], string='Tipo de Compensación', tracking=True)

    resolution_notes = fields.Text(
        string='Dictamen / Notas de Resolución',
        tracking=True,
    )
    resolved_by_id = fields.Many2one(
        'res.users',
        string='Resuelto por',
        readonly=True,
    )
    date_resolved = fields.Datetime(
        string='Fecha de Resolución',
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('b2b.order.claim') or _('New')
        records = super().create(vals_list)

        for record in records:
            claim_type_label = dict(record._fields['claim_type'].selection).get(record.claim_type, record.claim_type)
            prod_info = f"<br/><strong>Producto:</strong> {record.product_id.display_name} (Cant: {record.affected_qty})" if record.product_id else ""
            lot_info = f"<br/><strong>Lote:</strong> {record.lot_number}" if record.lot_number else ""

            # Registrar nota en el chatter del pedido de venta
            if record.order_id:
                record.order_id.message_post(
                    body=_(
                        "<strong>Reclamo B2B Ingresado: %(code)s</strong><br/>"
                        "<strong>Tipo:</strong> %(type)s"
                        "%(prod)s%(lot)s<br/>"
                        "<strong>Descripción:</strong> %(desc)s",
                        code=record.name,
                        type=claim_type_label,
                        prod=prod_info,
                        lot=lot_info,
                        desc=record.description,
                    ),
                    subtype_xmlid='mail.mt_note',
                )

            # Planificar actividad para el equipo de ventas / calidad
            activity_type = record.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if activity_type:
                target_user = record.order_id.user_id or record.env.user
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=target_user.id,
                    summary=_(
                        "Reclamo de entrega %(claim)s - %(partner)s (Pedido %(order)s)",
                        claim=record.name,
                        partner=record.commercial_partner_id.name or record.partner_id.name,
                        order=record.order_id.name,
                    ),
                    note=_(
                        "Se ha ingresado el reclamo <b>%(claim)s</b> por motivo <b>%(type)s</b>.<br/>"
                        "Revise la evidencia adjunta y determine el dictamen.",
                        claim=record.name,
                        type=claim_type_label,
                    ),
                )
        return records

    def action_set_in_progress(self):
        for rec in self:
            rec.write({'state': 'in_progress'})

    def action_resolve(self):
        self.ensure_one()
        if not self.resolution_type:
            raise UserError(_("Por favor, seleccione el Tipo de Compensación antes de resolver el reclamo."))
        self.write({
            'state': 'resolved',
            'resolved_by_id': self.env.user.id,
            'date_resolved': fields.Datetime.now(),
        })
        self.activity_feedback(['mail.mail_activity_data_todo'])

        res_type_label = dict(self._fields['resolution_type'].selection).get(self.resolution_type, self.resolution_type)
        if self.order_id:
            self.order_id.message_post(
                body=_(
                    "<strong>Reclamo %(code)s Resuelto</strong><br/>"
                    "<strong>Resolución:</strong> %(res)s<br/>"
                    "<strong>Notas:</strong> %(notes)s",
                    code=self.name,
                    res=res_type_label,
                    notes=self.resolution_notes or "Sin observaciones adicionales.",
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_reject(self):
        self.ensure_one()
        self.write({
            'state': 'rejected',
            'resolved_by_id': self.env.user.id,
            'date_resolved': fields.Datetime.now(),
        })
        self.activity_feedback(['mail.mail_activity_data_todo'])

        if self.order_id:
            self.order_id.message_post(
                body=_(
                    "<strong>Reclamo %(code)s Desestimado</strong><br/>"
                    "<strong>Motivo:</strong> %(notes)s",
                    code=self.name,
                    notes=self.resolution_notes or "Sin observaciones.",
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_reset_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})
