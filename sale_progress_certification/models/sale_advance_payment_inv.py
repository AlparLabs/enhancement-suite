from odoo import models, fields, _
from odoo.exceptions import UserError

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('percentage_progress', 'Certificación por % de avance')
        ],
        ondelete={'percentage_progress': 'set default'}
    )

    def create_invoices(self):
        # Si no es nuestra opción, dejamos que Odoo haga lo suyo
        if self.advance_payment_method != 'percentage_progress':
            return super().create_invoices()

        # Lógica personalizada para Certificación
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))


        for order in sale_orders:
            # Usamos el producto de anticipo estándar
            product_certification = order.company_id.sale_down_payment_product_id
            if not product_certification:
                raise UserError(_(
                    "No se encontró un producto de Anticipo configurado en la compañía. "
                    "Por favor asigne uno en Ventas > Configuración."
                ))

            # Calculamos el monto basado en el porcentaje ingresado en el wizard
            # pero utilizando el monto neto (untaxed) de la orden
            amount_to_invoice = order.amount_untaxed * (self.amount / 100.0)

            # Usamos el método nativo de crear línea de anticipo
            so_line = order._create_downpayment_line(
                product=product_certification,
                price=amount_to_invoice
            )
            
            # Personalizamos la descripción para que no diga "Anticipo" sino "Certificación"
            so_line.name = _('Certificación de Avance: %s%%') % (self.amount)
            
            # Creamos la factura de esa línea
            order._create_invoices(final=False)

        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()

        return {'type': 'ir.actions.act_window_close'}