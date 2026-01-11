from odoo import models, api, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Redefinimos invoice_ids para incluir out_receipt
    invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        compute='_compute_invoice_ids',
        search='_search_invoice_ids',
        copy=False,
    )

    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
    )

    @api.depends('order_line.invoice_lines')
    def _compute_invoice_ids(self):
        """
        Computa invoice_ids incluyendo facturas, notas de crédito Y recibos.
        """
        for order in self:
            # Buscamos por líneas vinculadas
            invoices = order.order_line.invoice_lines.move_id.filtered(
                lambda m: m.move_type in ('out_invoice', 'out_refund', 'out_receipt')
            )
            
            # Fallback: buscamos recibos por invoice_origin si no fueron encontrados por líneas
            receipt_by_origin = self.env['account.move'].search([
                ('invoice_origin', '=', order.name),
                ('move_type', '=', 'out_receipt'),
                ('state', '!=', 'cancel')
            ])
            
            # Unimos resultados
            order.invoice_ids = invoices | receipt_by_origin

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        """
        Computa el conteo de facturas incluyendo recibos.
        """
        for order in self:
            order.invoice_count = len(order.invoice_ids)

    def _search_invoice_ids(self, operator, value):
        """
        Permite buscar órdenes por sus facturas/recibos.
        """
        if operator == 'in':
            return [('order_line.invoice_lines.move_id', 'in', value)]
        return [('order_line.invoice_lines.move_id', operator, value)]

    def action_view_invoice(self, invoices=False):
        """
        Sobrescribimos la acción del botón inteligente para incluir Recibos (out_receipt)
        en la lista de documentos, no solo Facturas.
        """
        if not invoices:
            invoices = self.mapped('invoice_ids')
        
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
            action['res_id'] = False
            action['views'] = [
                (self.env.ref('account.view_out_invoice_tree').id, 'list'),
                (self.env.ref('account.view_move_form').id, 'form')
            ]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_partner_shipping_id': self.partner_shipping_id.id,
                'default_invoice_payment_term_id': self.payment_term_id.id or self.partner_id.property_payment_term_id.id or self.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
            })
        
        if len(invoices) > 1:
            context.pop('default_move_type', None)

        action['context'] = context
        return action