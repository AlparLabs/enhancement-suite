# account_payment_lock_3way/models/account_move.py
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

    # 2. Estado general de discrepancia (NUESTRA AUTORIDAD)
    # store=True para permitir búsquedas y filtros rápidos en la vista de lista
    x_discrepancy_state = fields.Selection([
        ('clean', 'Correcto'),
        ('discrepancy', 'Discrepancia')
    ], string="Estado 3-Way", compute="_compute_discrepancy_state", store=True)

    @api.depends('invoice_line_ids.is_3way_discrepancy')
    def _compute_discrepancy_state(self):
        """
        Calcula si la factura en general tiene problemas basado puramente en NUESTRA lógica.
        Independiente de la configuración nativa de Odoo.
        """
        for move in self:
            if any(move.invoice_line_ids.mapped('is_3way_discrepancy')):
                move.x_discrepancy_state = 'discrepancy'
            else:
                move.x_discrepancy_state = 'clean'

    def action_register_payment(self):
        """
        Intercepta el botón de pagar.
        Bloquea basado en 'x_discrepancy_state', ignorando 'release_to_pay' nativo.
        """
        for move in self:
            # Solo actuamos en Facturas de Proveedor que NUESTRO sistema marcó como discrepantes
            # Y que NO estén ya aprobadas manualmente
            if move.move_type == 'in_invoice' and move.x_discrepancy_state == 'discrepancy':
                
                # A. Válvula de escape: Aprobación Gerencial
                if move.x_force_payment_approved:
                    continue 

                # B. Verificación de Corrección Contable (NC/ND Aplicada)
                has_corrective_doc = False
                
                # Obtenemos las líneas de deuda (payable)
                payable_lines = move.line_ids.filtered(lambda l: l.account_type == 'liability_payable')
                
                # Buscamos en los cruces parciales
                partials = payable_lines.mapped('matched_debit_ids')
                
                for partial in partials:
                    counterpart_move = partial.credit_move_id.move_id
                    # Si está pagada/cruzada con una NC o una Factura Propia (ND), permitimos.
                    if counterpart_move.move_type in ['in_refund', 'out_invoice']:
                        has_corrective_doc = True
                        break
                
                if has_corrective_doc:
                    continue  # Tiene corrección aplicada, pase.

                # C. BLOQUEO DURO
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

    # 3. Campo computado por línea con lógica inteligente
    is_3way_discrepancy = fields.Boolean(
        string="Discrepancia 3-Way",
        compute="_compute_3way_discrepancy",
        store=True 
    )

    @api.depends('price_unit', 'quantity', 'product_id',
                 'purchase_line_id', 'purchase_line_id.price_unit', 
                 'purchase_line_id.qty_received', 'purchase_line_id.product_qty')
    def _compute_3way_discrepancy(self):
        """
        Compara Precio y Cantidad contra la PO.
        Soporta Servicios (Sobre Pedido) y Stock (Sobre Recibido).
        """
        for line in self:
            is_problem = False
            
            # Solo validamos si hay una Orden de Compra vinculada
            if line.purchase_line_id:
                
                # --- VALIDACIÓN DE PRECIO ---
                # ¿Precio Factura > Precio PO?
                if float_compare(line.price_unit, line.purchase_line_id.price_unit, precision_digits=2) == 1:
                    is_problem = True
                
                # --- VALIDACIÓN DE CANTIDAD ---
                else:
                    target_qty = 0.0
                    
                    # Lógica Inteligente:
                    # Si es Servicio/Sobre Pedido -> Comparamos con lo que pedimos (product_qty)
                    # Si es Stock/Sobre Recibido -> Comparamos con lo que llegó (qty_received)
                    if line.product_id.purchase_method == 'purchase':
                        target_qty = line.purchase_line_id.product_qty
                    else:
                        target_qty = line.purchase_line_id.qty_received

                    # ¿Cantidad Factura > Cantidad Objetivo?
                    if float_compare(line.quantity, target_qty, precision_digits=2) == 1:
                        is_problem = True

            line.is_3way_discrepancy = is_problem