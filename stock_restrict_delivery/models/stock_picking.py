from odoo import models, fields, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    force_no_invoice_delivery = fields.Boolean(
        string="Autorizar sin Factura",
        default=False,
        copy=False,
        tracking=True,
        help="Permite validar el albarán aunque la orden de venta no esté facturada."
    )

    def button_validate(self):
        for picking in self:
            # Validamos solo si es salida y viene de una venta
            if picking.picking_type_code == 'outgoing' and picking.sale_id:
                
                # Si el gerente autorizó, pasamos sin validar factura
                if picking.force_no_invoice_delivery:
                    return super(StockPicking, self).button_validate()

                # --- NUEVA LÓGICA STRICTA ---
                # Iteramos por cada movimiento para ver si su línea de venta asociada está facturada.
                # Solo nos importan productos con política 'order' (Facturar lo pedido).
                # Si es 'delivery', no podemos exigir factura antes de entregar (deadlock).
                
                for move in picking.move_ids:
                    if move.sale_line_id and move.sale_line_id.product_id.invoice_policy == 'order':
                        
                        # Cantidad que se intenta entregar ahora (usamos quantity o quantity_done según versión, probamos quantity)
                        # En Odoo moderno, 'quantity' en el move suele reflejar lo que se va a procesar si está reservado.
                        qty_to_deliver = move.quantity
                        
                        # Cantidad ya facturada en la línea de venta
                        qty_invoiced = move.sale_line_id.qty_invoiced
                        
                        # Cantidad ya entregada previamente
                        current_delivered = move.sale_line_id.qty_delivered
                        
                        # Lo que habrá entregado en total después de esta validación
                        future_delivered = current_delivered + qty_to_deliver
                        
                        # Permitimos una pequeña tolerancia por redondeo (0.01)
                        # Si (qty_invoiced < future_delivered) -> Error
                        if float_compare(qty_invoiced, future_delivered, precision_digits=2) == -1:
                             raise ValidationError(_(
                                "🛑 BLOQUEO DE ENTREGA (Estricto)\n\n"
                                "El producto '%s' requiere facturación previa (Política: Sobre Pedido).\n"
                                "- Cantidad a entregar (acumulada): %s\n"
                                "- Cantidad facturada: %s\n\n"
                                "Falta facturar %s unidades para proceder.\n"
                                "SOLUCIÓN: Publique la factura por la cantidad restante o solicite autorización gerencial."
                            ) % (move.product_id.name, future_delivered, qty_invoiced, future_delivered - qty_invoiced))

        return super(StockPicking, self).button_validate()