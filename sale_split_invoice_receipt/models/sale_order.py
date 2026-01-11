from odoo import models, api, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    @api.depends('order_line.invoice_lines')
    def _get_invoiced(self):
        """
        Sobrescribimos para incluir Recibos (out_receipt) en invoice_ids.
        """
        # Primero llamamos al método original para que setee invoice_ids estándar
        super(SaleOrder, self)._get_invoiced()
        
        # Ahora añadimos los recibos a cada orden
        for order in self:
            # Buscamos recibos vinculados por líneas
            receipts = self.env['account.move'].search([
                ('line_ids.sale_line_ids.order_id', '=', order.id),
                ('move_type', '=', 'out_receipt'),
                ('state', '!=', 'cancel')
            ])
            
            # Si no encontramos por líneas, intentamos por origen
            if not receipts:
                receipts = self.env['account.move'].search([
                    ('invoice_origin', '=', order.name),
                    ('move_type', '=', 'out_receipt'),
                    ('state', '!=', 'cancel')
                ])
            
            # Añadimos los recibos a invoice_ids (si existen)
            if receipts:
                order.invoice_ids = order.invoice_ids | receipts