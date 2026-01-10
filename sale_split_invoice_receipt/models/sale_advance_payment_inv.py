from odoo import models, fields, _
from odoo.exceptions import UserError

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"  # Esto es el Odoo Base, no el otro módulo

    advance_payment_method = fields.Selection(
        selection_add=[
            ('split_50_50', 'Dividir: 50% Factura / 50% Recibo X')
        ],
        ondelete={'split_50_50': 'set default'}
    )

    def create_invoices(self):
        # Si el usuario no eligió nuestra opción, dejamos que Odoo haga lo suyo
        if self.advance_payment_method != 'split_50_50':
            return super().create_invoices()

        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        company = self.env.company

        # Verificamos producto de anticipo (Configuración estándar de Odoo Ventas)
        if not company.sale_down_payment_product_id:
            raise UserError(_("Por favor configure el 'Producto de Anticipo' en los Ajustes de Ventas."))

        product_down = company.sale_down_payment_product_id
        created_moves = self.env['account.move']

        for order in sale_orders:
            # 1. Calculamos mitades
            half_amount = order.amount_total * 0.50

            # --- A. PARTE OFICIAL (Factura A/B) ---
            line_a = order._create_downpayment_line(product=product_down, price=half_amount)
            line_a.name = _('Anticipo 50% (Fiscal)')
            
            # Genera la factura solo por este monto
            invoice_a = order._create_invoices(final=False)
            created_moves += invoice_a

            # --- B. PARTE PRESUPUESTO (Recibo X) ---
            line_b = order._create_downpayment_line(product=product_down, price=half_amount)
            line_b.name = _('Saldo 50% (Presupuesto X)')
            
            # Genera factura borrador por el resto
            invoice_b_set = order._create_invoices(final=False)
            invoice_b = invoice_b_set - invoice_a # Filtramos para obtener la nueva
            
            if invoice_b:
                # --- AQUÍ USAMOS TU OTRO MÓDULO ---
                # Llamamos a la función que ya creaste en 'account_invoice_to_receipt'.
                # Esto automáticamente busca el diario que configuraste en ese módulo,
                # convierte a Recibo, quita impuestos y limpia datos fiscales.
                invoice_b.action_convert_to_internal_receipt()
                
                # Le ponemos una referencia clara
                invoice_b.ref = _('Ref. Presupuesto %s') % order.name
                created_moves += invoice_b

        # Abrimos las facturas generadas
        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()

        return {'type': 'ir.actions.act_window_close'}