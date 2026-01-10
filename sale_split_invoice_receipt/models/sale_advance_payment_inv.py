from odoo import models, fields, _
from odoo.exceptions import UserError

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('split_50_50', 'Dividir Cantidades: 50% Oficial / 50% Recibo X')
        ],
        ondelete={'split_50_50': 'set default'}
    )

    def create_invoices(self):
        # 1. Si no es nuestra opción, comportamiento estándar
        if self.advance_payment_method != 'split_50_50':
            return super().create_invoices()

        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        created_moves = self.env['account.move']

        for order in sale_orders:
            if order.invoice_status == 'invoiced':
                continue

            # --- A. PREPARAR FACTURA OFICIAL (50%) ---
            invoice_vals_a = order._prepare_invoice()
            invoice_lines_a = []

            # --- B. PREPARAR RECIBO (50%) ---
            invoice_vals_b = order._prepare_invoice()
            invoice_lines_b = []

            # Iteramos sobre las líneas del pedido
            for line in order.order_line:
                # Ignoramos notas, secciones o líneas con cantidad 0
                if line.display_type or line.product_uom_qty == 0.0:
                    continue

                # Preparamos la data base de la línea (cuentas, impuestos, nombre)
                # Odoo por defecto trae 'qty_to_invoice', pero nosotros forzaremos la mitad
                original_line_vals = line._prepare_invoice_line()
                
                # Calculamos mitad
                half_qty = line.product_uom_qty * 0.5

                # Línea para Factura A
                vals_a = original_line_vals.copy()
                vals_a['quantity'] = half_qty
                invoice_lines_a.append((0, 0, vals_a))

                # Línea para Factura B
                vals_b = original_line_vals.copy()
                vals_b['quantity'] = half_qty
                invoice_lines_b.append((0, 0, vals_b))

            # Si no hay líneas facturables, pasamos
            if not invoice_lines_a:
                continue

            # --- CREACIÓN DOCUMENTO A (Oficial) ---
            invoice_vals_a['invoice_line_ids'] = invoice_lines_a
            move_a = self.env['account.move'].create(invoice_vals_a)
            created_moves += move_a

            # --- CREACIÓN DOCUMENTO B (Recibo) ---
            invoice_vals_b['invoice_line_ids'] = invoice_lines_b
            move_b = self.env['account.move'].create(invoice_vals_b)
            
            # Aplicamos la conversión usando tu módulo 'account_invoice_to_receipt'
            # Esto cambiará el diario, quitará impuestos y ajustará el tipo
            try:
                move_b.action_convert_to_internal_receipt()
                
                # Referencia visual
                move_b.ref = _('Ref. Presupuesto %s (50%%)') % order.name
                created_moves += move_b
                
            except UserError as e:
                # Si falla la conversión (ej. falta configurar diario), borramos la factura B para no dejar basura
                move_b.unlink()
                raise UserError(_("Se creó la factura oficial, pero falló la creación del recibo: %s") % str(e))

        # Abrimos las facturas generadas
        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()

        return {'type': 'ir.actions.act_window_close'}