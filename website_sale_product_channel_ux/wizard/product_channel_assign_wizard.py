import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductChannelAssignWizard(models.TransientModel):
    _name = 'product.channel.assign.wizard'
    _description = 'Asistente de Asignación Masiva de Canal Web'

    @api.model
    def _default_product_tmpl_ids(self):
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')
        if active_model == 'product.template':
            return [(6, 0, active_ids)]
        elif active_model == 'product.product':
            tmpl_ids = self.env['product.product'].browse(active_ids).mapped('product_tmpl_id').ids
            return [(6, 0, tmpl_ids)]
        return []

    product_tmpl_ids = fields.Many2many(
        'product.template',
        string='Productos Seleccionados',
        default=_default_product_tmpl_ids,
    )
    product_count = fields.Integer(
        string='Cantidad de Productos',
        compute='_compute_product_count',
    )
    action_type = fields.Selection(
        [
            ('assign', 'Asignar a un Canal Específico'),
            ('clear', 'Habilitar para Ambos Canales (Sin restricción)'),
        ],
        string='Acción',
        default='assign',
        required=True,
    )
    website_id = fields.Many2one(
        'website',
        string='Canal Web / Sitio',
        help='Sitio web donde estarán disponibles los productos seleccionados.',
    )

    @api.depends('product_tmpl_ids')
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_tmpl_ids)

    def action_apply(self):
        self.ensure_one()
        if not self.product_tmpl_ids:
            raise UserError(_("No hay productos seleccionados para actualizar."))
        if self.action_type == 'assign' and not self.website_id:
            raise UserError(_("Por favor, seleccione el Canal Web de destino."))

        target_website = self.website_id.id if self.action_type == 'assign' else False
        self.product_tmpl_ids.write({'website_id': target_website})

        msg = (
            _("Se asignaron %d producto(s) al canal '%s'.") % (len(self.product_tmpl_ids), self.website_id.name)
            if self.action_type == 'assign'
            else _("Se configuraron %d producto(s) disponibles para Ambos Canales (Todos).") % len(self.product_tmpl_ids)
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Canales Actualizados"),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
