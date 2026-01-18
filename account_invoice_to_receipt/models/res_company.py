from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    # --- Configuración Clientes ---
    receipt_customer_journal_id = fields.Many2one('account.journal', string="Diario Recibo (Clientes)")
    receipt_customer_account_id = fields.Many2one('account.account', string="Cta. Contrapartida (Clientes)")
    receipt_customer_product_account_id = fields.Many2one('account.account', string="Cta. Producto (Clientes)")
    receipt_customer_tax_id = fields.Many2one('account.tax', string="Impuesto Fijo (Clientes)")
    

    # --- Configuración Proveedores ---
    receipt_vendor_journal_id = fields.Many2one('account.journal', string="Diario Recibo (Proveedores)")
    receipt_vendor_account_id = fields.Many2one('account.account', string="Cta. Contrapartida (Proveedores)")
    receipt_vendor_product_account_id = fields.Many2one('account.account', string="Cta. Producto (Proveedores)")
    receipt_vendor_tax_id = fields.Many2one('account.tax', string="Impuesto Fijo (Proveedores)")