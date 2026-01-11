import copy

from odoo import models, fields, _
from odoo.exceptions import UserError

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('split_50_50', 'Dividir Cantidades: 50% Oficial / 50% Recibo X'),
            ('receipt', 'Recibo X (Completo)')
        ],
        ondelete={'split_50_50': 'set default', 'receipt': 'set default'}
    )

    def create_invoices(self):
        # 1. Si no es nuestra opción, comportamiento estándar
        if self.advance_payment_method not in ('split_50_50', 'receipt'):
            return super().create_invoices()

        # CASO RECIBO COMPLETO
        if self.advance_payment_method == 'receipt':
            # Creamos las facturas estándar usando la lógica nativa
            action = super().create_invoices()
            
            # Recuperamos los movimientos creados
            moves = self.env['account.move']
            if isinstance(action, dict):
                if action.get('res_id'):
                    moves = self.env['account.move'].browse(action['res_id'])
                elif action.get('domain'):
                    # Intentamos extraer los IDs del dominio
                    domain = action['domain']
                    move_ids = []
                    for leaf in domain:
                        if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'id' and leaf[1] == 'in':
                            move_ids = leaf[2]
                            break
                    if move_ids:
                        moves = self.env['account.move'].browse(move_ids)
            
            if not moves:
                # Fallback: buscamos por contexto active_ids si no podemos deducirlo de la acción
                sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
                moves = sale_orders.invoice_ids.filtered(lambda m: m.state == 'draft' and m.create_date >= fields.Datetime.now())

            # Convertimos a Recibo
            for move in moves:
                if move.move_type == 'out_invoice':
                    move.action_convert_to_internal_receipt()
                    move.ref = _('Recibo X de %s') % move.invoice_origin

            return action

        # CASO SPLIT 50/50
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