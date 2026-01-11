from odoo import models, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_invoiced(self):
        """
        Sobrescribimos para que los Recibos de Venta (out_receipt) también sumen
        a la cantidad facturada del pedido, no solo las facturas oficiales.
        """
        # 1. Primero dejamos que Odoo calcule lo estándar (Facturas y Notas de Crédito)
        super(SaleOrderLine, self)._compute_qty_invoiced()

        # 2. Ahora recorremos y sumamos lo que esté en 'out_receipt'
        for line in self:
            qty_receipts = 0.0
            for inv_line in line.invoice_lines:
                # Condición: Que sea Recibo (out_receipt) y no esté Cancelado
                if inv_line.move_id.state != 'cancel' and inv_line.move_id.move_type == 'out_receipt':
                    
                    # Si las unidades de medida coinciden, sumamos directo
                    if inv_line.product_uom_id == line.product_uom:
                        qty_receipts += inv_line.quantity
                    else:
                        # Si son distintas, convertimos (ej: docenas a unidades)
                        qty_receipts += inv_line.product_uom_id._compute_quantity(
                            inv_line.quantity, line.product_uom
                        )
            
            # 3. Sumamos el extra encontrado a lo que ya calculó Odoo
            line.qty_invoiced += qty_receipts