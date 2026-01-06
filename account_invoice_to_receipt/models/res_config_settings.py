from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Clientes
    receipt_customer_journal_id = fields.Many2one(related='company_id.receipt_customer_journal_id', readonly=False)
    receipt_customer_account_id = fields.Many2one(related='company_id.receipt_customer_account_id', readonly=False)
    receipt_customer_tax_id = fields.Many2one(related='company_id.receipt_customer_tax_id', readonly=False)

    # Proveedores
    receipt_vendor_journal_id = fields.Many2one(related='company_id.receipt_vendor_journal_id', readonly=False)
    receipt_vendor_account_id = fields.Many2one(related='company_id.receipt_vendor_account_id', readonly=False)
    receipt_vendor_tax_id = fields.Many2one(related='company_id.receipt_vendor_tax_id', readonly=False)