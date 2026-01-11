import copy

from odoo import models, fields, _
from odoo.exceptions import UserError

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('split_50_50', 'Dividir documento: 50% Oficial / 50% Presupuesto'),
            ('receipt', 'Presupuesto')
        ],
        ondelete={'split_50_50': 'set default', 'receipt': 'set default'}
    )

    def create_invoices(self):
        # 1. Si no es nuestra opción, comportamiento estándar
        if self.advance_payment_method not in ('split_50_50', 'receipt'):
            return super().create_invoices()

        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        created_moves = self.env['account.move']

        # CASO RECIBO COMPLETO (100%)
        if self.advance_payment_method == 'receipt':
            for order in sale_orders:
                if order.invoice_status == 'invoiced':
                    continue

                # Preparar factura base
                invoice_vals = order._prepare_invoice()
                invoice_lines = []

                # Iteramos sobre las líneas del pedido
                for line in order.order_line:
                    # Ignoramos notas, secciones o líneas sin cantidad a facturar
                    if line.display_type or line.qty_to_invoice <= 0.0:
                        continue

                    # Preparamos la línea con los datos reales
                    line_vals = line._prepare_invoice_line()
                    line_vals['quantity'] = line.qty_to_invoice
                    invoice_lines.append((0, 0, line_vals))

                # Si no hay líneas facturables, pasamos
                if not invoice_lines:
                    continue

                # Crear la factura con las líneas reales
                invoice_vals['invoice_line_ids'] = invoice_lines
                move = self.env['account.move'].create(invoice_vals)

                # Convertir a Recibo usando el módulo account_invoice_to_receipt
                try:
                    move.action_convert_to_internal_receipt()
                    move.ref = _('Presupuesto de %s') % order.name
                    created_moves += move
                except UserError as e:
                    move.unlink()
                    raise UserError(_("Falló la creación del Presupuesto: %s") % str(e))

            # Abrimos los documentos generados
            if self._context.get('open_invoices', False) and created_moves:
                return sale_orders.action_view_invoice(invoices=created_moves)

            return {'type': 'ir.actions.act_window_close'}

        # CASO SPLIT 50/50
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
                # Ignoramos notas, secciones o líneas sin cantidad a facturar
                if line.display_type or line.qty_to_invoice <= 0.0:
                    continue

                # Preparamos la data base de la línea (cuentas, impuestos, nombre)
                original_line_vals = line._prepare_invoice_line()
                
                # Calculamos mitad de lo pendiente por facturar
                half_qty = line.qty_to_invoice * 0.5

                # Línea para Factura A (usamos deepcopy para evitar compartir referencias)
                vals_a = copy.deepcopy(original_line_vals)
                vals_a['quantity'] = half_qty
                invoice_lines_a.append((0, 0, vals_a))

                # Línea para Factura B
                vals_b = copy.deepcopy(original_line_vals)
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
            try:
                move_b.action_convert_to_internal_receipt()
                move_b.ref = _('Ref. Presupuesto %s (50%%)') % order.name
                created_moves += move_b
            except UserError as e:
                move_b.unlink()
                raise UserError(_("Se creó la factura oficial, pero falló la creación del Presupuesto: %s") % str(e))

        # Abrimos las facturas generadas
        if self._context.get('open_invoices', False) and created_moves:
            return sale_orders.action_view_invoice(invoices=created_moves)

        return {'type': 'ir.actions.act_window_close'}