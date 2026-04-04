from odoo import models, fields, _
from odoo.exceptions import UserError

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('percentage_progress', 'Certificación por % de avance'),
            ('fixed_progress', 'Certificación por Monto Fijo (Neto)')
        ],
        ondelete={
            'percentage_progress': 'set default',
            'fixed_progress': 'set default'
        }
    )

    def create_invoices(self):
        # Si no es nuestra opción, dejamos que Odoo haga lo suyo
        if self.advance_payment_method not in ('percentage_progress', 'fixed_progress'):
            return super().create_invoices()

        # Lógica personalizada para Certificación
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        # Buscamos el producto definido en el XML data
        product_certification = self.env.ref(
            'sale_progress_certification.product_product_certification', 
            raise_if_not_found=False
        )
        
        # Fallback de seguridad
        if not product_certification:
            raise UserError(_(
                "No se encontró el producto de Certificación definido en los datos del módulo. "
                "Por favor reinstale el módulo o verifique que el producto no fue archivado."
            ))

        invoices = self.env['account.move']
        for order in sale_orders:
            # Calculamos el monto dependiendo de la opción
            if self.advance_payment_method == 'percentage_progress':
                # Nativamente % es sobre monto total. Si lo prefieren sobre otra cosa, podemos ajustarlo
                amount_to_invoice = order.amount_total * (self.amount / 100.0)
                description = _('Certificación de Avance: %s%%') % (self.amount)
            else:
                amount_to_invoice = self.fixed_amount
                description = _('Certificación de Avance: Monto Fijo')

            # Crear sección si no existe
            if not any(line.display_type == 'line_section' and line.is_downpayment for line in order.order_line):
                self.env['sale.order.line'].create({
                    'name': _('Certificaciones'),
                    'product_uom_qty': 0.0,
                    'order_id': order.id,
                    'display_type': 'line_section',
                    'is_downpayment': True,
                    'sequence': order.order_line and order.order_line[-1].sequence + 1 or 10,
                })

            so_line = self.env['sale.order.line'].create({
                'name': description,
                'price_unit': amount_to_invoice,
                'product_uom_qty': 0.0,
                'order_id': order.id,
                'discount': 0.0,
                'product_uom': product_certification.uom_id.id,
                'product_id': product_certification.id,
                'tax_id': [(6, 0, product_certification.taxes_id.ids)],
                'is_downpayment': True,
                'sequence': order.order_line and order.order_line[-1].sequence + 1 or 10,
            })
            
            # Creamos la factura vinculada a esta línea explícitamente
            invoice_vals = {
                **order._prepare_invoice(),
                'invoice_line_ids': [(0, 0, so_line._prepare_invoice_line(
                    name=description,
                    quantity=1.0,
                ))]
            }
            invoice = self.env['account.move'].sudo().create(invoice_vals)
            
            # Mensaje en chatter
            invoice = invoice.sudo(self.env.su)
            invoice.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': invoice, 'origin': order},
                subtype_xmlid='mail.mt_note',
            )
            invoices += invoice

        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice(invoices=invoices)

        return {'type': 'ir.actions.act_window_close'}