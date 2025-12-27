# account_payment_lock_3way/models/account_move.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Campo de control para gerentes
    x_force_payment_approved = fields.Boolean(
        string="Autorizar Pago (Forzar)",
        tracking=True,
        help="Permite registrar el pago aunque existan discrepancias en el 3-Way Match."
    )

    def action_register_payment(self):
        """
        Intercepta el botón de pagar.
        Verifica:
        1. ¿Es factura de proveedor?
        2. ¿Tiene excepción de 3-way match?
        3. ¿Tiene aprobación manual O corrección aplicada (NC/ND)?
        """
        for move in self:
            # Solo actuamos en Facturas de Proveedor con estado 'Excepción'
            if move.move_type == 'in_invoice' and move.release_to_pay == 'exception':
                
                # --- VÍA 1: Aprobación Gerencial ---
                if move.x_force_payment_approved:
                    continue  # Pasa al siguiente o al super()

                # --- VÍA 2: Corrección Contable (NC/ND Aplicada) ---
                has_corrective_doc = False
                
                # Obtenemos las líneas de deuda (payable)
                payable_lines = move.line_ids.filtered(lambda l: l.account_type == 'liability_payable')
                
                # Buscamos en los pagos/cruces parciales ya conciliados
                # matched_debit_ids = Documentos que reducen la deuda de esta factura
                partials = payable_lines.mapped('matched_debit_ids')
                
                for partial in partials:
                    # Buscamos el documento que originó este cruce (la contraparte)
                    # En un cruce, debit_move_id es la factura, credit_move_id es el pago/NC
                    counterpart_move = partial.credit_move_id.move_id
                    
                    # Verificamos el tipo de documento de la contraparte
                    # 'in_refund': Nota de Crédito de Proveedor
                    # 'out_invoice': Factura a Cliente (si le facturamos al proveedor para cruzar cuentas)
                    if counterpart_move.move_type in ['in_refund', 'out_invoice']:
                        has_corrective_doc = True
                        break
                
                if has_corrective_doc:
                    continue  # Se encontró una corrección aplicada, permitimos pagar el resto.

                # --- BLOQUEO ---
                raise UserError(_(
                    "⛔ PAGO BLOQUEADO POR DISCREPANCIA (3-Way Match)\n\n"
                    "El sistema detectó diferencias en Precio o Cantidad respecto a la Orden de Compra.\n"
                    "Para proceder, realice una de las siguientes acciones:\n"
                    "1. Aplique (concilie) una Nota de Crédito del proveedor a esta factura.\n"
                    "2. Aplique una Factura Cruzada (Nota de Débito).\n"
                    "3. Solicite autorización marcando 'Autorizar Pago' (Solo Gerentes)."
                ))

        return super(AccountMove, self).action_register_payment()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Campos espejo para poder usarlos en la vista XML (JavaScript)
    x_purchase_price_unit = fields.Float(
        related='purchase_line_id.price_unit', 
        string="Precio Original PO",
        readonly=True
    )
    x_purchase_qty_received = fields.Float(
        related='purchase_line_id.qty_received', 
        string="Cant. Recibida PO",
        readonly=True
    )