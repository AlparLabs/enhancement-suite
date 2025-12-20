from odoo import models, fields, _
from odoo.exceptions import ValidationError

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

                # Buscamos facturas publicadas
                invoices_posted = picking.sale_id.invoice_ids.filtered(lambda i: i.state == 'posted')
                
                if not invoices_posted:
                    raise ValidationError(_(
                        "🛑 BLOQUEO DE ENTREGA\n\n"
                        "La Orden de Venta (%s) no tiene una factura publicada.\n"
                        "Por política de la empresa, no se puede entregar mercadería sin facturar.\n\n"
                        "SOLUCIÓN: Solicite a un Gerente que marque 'Autorizar sin Factura' en la pestaña 'Otra Información'."
                    ) % picking.sale_id.name)
                    
        return super(StockPicking, self).button_validate()