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


        for order in sale_orders:
            # Obtenemos el producto de anticipo estándar
            # En Odoo 17/18, suele estar en el wizard (self.product_id) o en ir.config_parameter
            product_certification = getattr(self, 'product_id', False)
            if not product_certification:
                dp_id = self.env['ir.config_parameter'].sudo().get_param('sale.default_deposit_product_id')
                if dp_id:
                    product_certification = self.env['product.product'].browse(int(dp_id))
            
            if not product_certification:
                raise UserError(_(
                    "No se encontró un producto de Anticipo configurado en la compañía o el sistema. "
                    "Por favor asigne uno en Ventas > Configuración."
                ))

            # Calculamos el monto dependiendo de la opción
            if self.advance_payment_method == 'percentage_progress':
                # Según lo charlado, se utiliza el monto neto (untaxed) para certif.
                amount_to_invoice = order.amount_untaxed * (self.amount / 100.0)
                description = _('Certificación de Avance: %s%%') % (self.amount)
            else:
                amount_to_invoice = self.fixed_amount
                description = _('Certificación de Avance: Monto Fijo')

            # Usamos el método nativo de crear línea de anticipo (estándar de Odoo)
            so_line = order._create_downpayment_line(
                product=product_certification,
                price=amount_to_invoice
            )
            
            # Personalizamos la descripción
            so_line.name = description
            
            # Creamos la factura usando el método estándar
            order._create_invoices(final=False)

        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()

        return {'type': 'ir.actions.act_window_close'}