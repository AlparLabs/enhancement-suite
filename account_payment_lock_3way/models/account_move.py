from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

class AccountMove(models.Model):
    _inherit = 'account.move'

    # 1. Campo para "forzar" el pago manualmente (Solo Gerentes)
    x_force_payment_approved = fields.Boolean(
        string="Autorizar Pago (Forzar)",
        tracking=True,
        help="Permite registrar el pago aunque existan discrepancias en el 3-Way Match."
    )

    # 2. Estado general de discrepancia (Para filtros, búsquedas y el Badge de colores)
    x_discrepancy_state = fields.Selection([
        ('clean', 'Correcto'),
        ('discrepancy', 'Discrepancia')
    ], string="Estado 3-Way", compute="_compute_discrepancy_state", store=True)

    @api.depends('invoice_line_ids.is_3way_discrepancy')
    def _compute_discrepancy_state(self):
        """
        Calcula si la factura en general tiene problemas.
        Si al menos una línea tiene discrepancia, toda la factura se marca como 'discrepancy'.
        """
        for move in self:
            # Buscamos si existe alguna línea con el flag en True
            if any(move.invoice_line_ids.mapped('is_3way_discrepancy')):
                move.x_discrepancy_state = 'discrepancy'
            else:
                move.x_discrepancy_state = 'clean'

    def action_register_payment(self):
        """
        Intercepta el botón de pagar para bloquear si hay discrepancias no resueltas.
        """
        for move in self:
            # Solo actuamos en Facturas de Proveedor con estado de excepción de Odoo
            if move.move_type == 'in_invoice' and move.release_to_pay == 'exception':
                
                # A. Válvula de escape: Aprobación Gerencial
                if move.x_force_payment_approved:
                    continue 

                # B. Verificación de Corrección Contable (NC/ND Aplicada)
                # Si el sistema marca discrepancia visualmente, verificamos si ya se "pagó" con una NC
                if move.x_discrepancy_state == 'discrepancy':
                    
                    has_corrective_doc = False
                    
                    # Obtenemos las líneas de deuda (payable)
                    payable_lines = move.line_ids.filtered(lambda l: l.account_type == 'liability_payable')
                    
                    # Buscamos en los cruces parciales (pagos/NCs ya aplicados)
                    partials = payable_lines.mapped('matched_debit_ids')
                    
                    for partial in partials:
                        # Buscamos la contraparte (el documento que está ajustando esta factura)
                        counterpart_move = partial.credit_move_id.move_id
                        
                        # Tipos de documentos que consideramos "Corrección Válida":
                        # 'in_refund': Nota de Crédito de Proveedor
                        # 'out_invoice': Factura a Cliente (Factura Cruzada / Nota de Débito propia)
                        if counterpart_move.move_type in ['in_refund', 'out_invoice']:
                            has_corrective_doc = True
                            break
                    
                    if has_corrective_doc:
                        continue  # Se encontró corrección, permitimos pagar el saldo restante.

                    # C. BLOQUEO FINAL
                    raise UserError(_(
                        "⛔ PAGO BLOQUEADO POR DISCREPANCIA (3-Way Match)\n\n"
                        "El sistema detectó diferencias en Precio o Cantidad respecto a la Orden de Compra.\n"
                        "Estado actual: Discrepancia.\n\n"
                        "Para proceder, realice una de las siguientes acciones:\n"
                        "1. Aplique (concilie) una Nota de Crédito del proveedor.\n"
                        "2. Aplique una Factura Cruzada (Nota de Débito).\n"
                        "3. Solicite autorización marcando 'Autorizar Pago' (Solo Gerentes)."
                    ))

        return super(AccountMove, self).action_register_payment()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # 3. Campo computado por línea: ¿Esta línea específica tiene problemas?
    is_3way_discrepancy = fields.Boolean(
        string="Discrepancia 3-Way",
        compute="_compute_3way_discrepancy",
        store=True # Guardado para permitir búsquedas rápidas y rendimiento
    )

    @api.depends('price_unit', 'quantity', 'product_id', # Agregamos product_id a las dependencias
                 'purchase_line_id', 'purchase_line_id.price_unit', 
                 'purchase_line_id.qty_received', 'purchase_line_id.product_qty')
    def _compute_3way_discrepancy(self):
        """
        Lógica mejorada: Se adapta a la política de control del producto (Pedido vs Recibido).
        """
        for line in self:
            is_problem = False
            
            if line.purchase_line_id:
                
                # 1. Validar Precio (Siempre igual: Factura vs PO)
                if float_compare(line.price_unit, line.purchase_line_id.price_unit, precision_digits=2) == 1:
                    is_problem = True
                
                # 2. Validar Cantidad (INTELIGENTE)
                else:
                    # Determinamos contra qué comparar según la configuración del producto
                    # purchase_method: 'purchase' (Sobre pedido) | 'receive' (Sobre recibido)
                    
                    target_qty = 0.0
                    
                    # Si el producto se controla por "Cantidades Pedidas" (Servicios usualmente)
                    if line.product_id.purchase_method == 'purchase':
                        target_qty = line.purchase_line_id.product_qty
                    
                    # Si el producto se controla por "Cantidades Recibidas" (Stock)
                    else:
                        target_qty = line.purchase_line_id.qty_received

                    # Comparación final
                    if float_compare(line.quantity, target_qty, precision_digits=2) == 1:
                        is_problem = True

            line.is_3way_discrepancy = is_problem