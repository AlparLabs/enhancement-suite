# alpardata/enhancement-suite/enhancement-suite-bb42944636a0a9baa7494990cb9adf4bb41607ac/account_invoice_to_receipt/models/account_move.py

from odoo import models, fields, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_convert_to_internal_receipt(self):
        """ Convierte Factura Borrador a Recibo Interno usando config de la compañía """
        for move in self:
            if move.state != 'draft':
                continue

            company = move.company_id
            vals = {}
            target_type = False
            config_journal = False
            config_account = False
            config_product_account = False # Nueva variable
            config_tax = False
            contra_type = False

            # 1. Definir configuración según tipo
            if move.move_type in ['out_invoice', 'out_receipt']:
                target_type = 'out_receipt'
                config_journal = company.receipt_customer_journal_id
                config_account = company.receipt_customer_account_id
                config_product_account = company.receipt_customer_product_account_id
                config_tax = company.receipt_customer_tax_id
                contra_type = 'asset_receivable'
                doc_type = 'Cliente'
            elif move.move_type in ['in_invoice', 'in_receipt']:
                target_type = 'in_receipt'
                config_journal = company.receipt_vendor_journal_id
                config_account = company.receipt_vendor_account_id
                config_product_account = company.receipt_vendor_product_account_id
                config_tax = company.receipt_vendor_tax_id
                contra_type = 'liability_payable'
                doc_type = 'Proveedor'
            else:
                continue # No es factura ni recibo

            # 2. Validar que exista configuración mínima
            if not config_journal or not config_account:
                raise UserError(_(
                    "Falta configuración para %s en la empresa %s.\n"
                    "Ve a Ajustes > Contabilidad > Conversión a Recibos."
                ) % (doc_type, company.name))

            # 3. Preparar cambio de cabecera
            vals['journal_id'] = config_journal.id
            
            # Cambio de tipo y limpieza LATAM
            if move.move_type != target_type:
                vals['move_type'] = target_type
                # Borrar tipo de documento LATAM (Factura A/B) si existe el campo
                if 'l10n_latam_document_type_id' in move:
                    vals['l10n_latam_document_type_id'] = False
            
            # Parche número documento proveedor
            if target_type == 'in_receipt' and not move.l10n_latam_document_number:
                vals['l10n_latam_document_number'] = '000-%s' % move.id

            move.write(vals)

            # 4. Actualizar Líneas de Producto (Cuentas e Impuestos)
            product_lines = move.line_ids.filtered(lambda l: l.display_type == 'product')
            
            # A. IMPUESTOS
            if config_tax:
                product_lines.write({'tax_ids': [(6, 0, [config_tax.id])]})
            else:
                product_lines.write({'tax_ids': [(5, 0, 0)]})

            # B. CUENTAS CONTABLES DE PRODUCTO
            if config_product_account:
                # CASO 1: Usar la cuenta "pre-establecida" para TODAS las líneas
                product_lines.write({'account_id': config_product_account.id})
            else:
                # CASO 2: Restaurar original del producto (Comportamiento por defecto)
                for line in product_lines:
                    prod = line.product_id
                    if not prod: continue
                    
                    account = False
                    if target_type == 'out_receipt':
                        account = prod.property_account_income_id or prod.categ_id.property_account_income_categ_id
                    else:
                        account = prod.property_account_expense_id or prod.categ_id.property_account_expense_categ_id
                    
                    if account:
                        line.write({'account_id': account.id})

            # 5. Actualizar Contrapartida (Cobrar/Pagar)
            # Buscamos la línea que tenga el tipo de cuenta receivable/payable
            contra_line = move.line_ids.filtered(lambda l: l.account_id.account_type == contra_type)
            if len(contra_line) == 1:
                contra_line.write({'account_id': config_account.id})

            # 6. Log en el chatter
            move.message_post(body=_(
                "Documento convertido a <b>Recibo Interno</b>.<br/>"
                "Diario: %s<br/>"
                "Cuenta Producto: %s"
            ) % (config_journal.name, config_product_account.name if config_product_account else "Original"))