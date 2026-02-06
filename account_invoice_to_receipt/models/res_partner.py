# res_partner.py
# Extends total_invoiced and action to include receipts

from odoo import models, api, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Redeclare the field with our compute method
    total_invoiced = fields.Monetary(
        compute='_compute_total_invoiced',
        string="Total Invoiced",
        groups='account.group_account_invoice,account.group_account_readonly',
    )

    def _compute_total_invoiced(self):
        """Override to include out_receipt in the total invoiced calculation."""
        if not self.ids:
            self.total_invoiced = 0
            return

        all_partners_children = self.with_context(active_test=False).search([
            ('id', 'child_of', self.ids)
        ])
        all_partner_ids = all_partners_children.ids

        # Domain that includes out_invoice, out_refund, AND out_receipt
        self.env['account.move'].flush_model(['amount_total_signed', 'partner_id', 'move_type', 'state'])
        
        self._cr.execute("""
            SELECT partner_id, SUM(amount_total_signed)
            FROM account_move
            WHERE partner_id IN %s
              AND move_type IN ('out_invoice', 'out_refund', 'out_receipt')
              AND state = 'posted'
            GROUP BY partner_id
        """, [tuple(all_partner_ids)])
        
        amounts = dict(self._cr.fetchall())
        
        for partner in self:
            partner_ids = partner.with_context(active_test=False).search([
                ('id', 'child_of', partner.id)
            ]).ids
            partner.total_invoiced = sum(amounts.get(pid, 0) for pid in partner_ids)

    def action_view_partner_invoices(self):
        """Override to include out_receipt in the invoices view."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        
        # Extend the domain to include out_receipt
        action['domain'] = [
            ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
            ('partner_id', 'child_of', self.id),
        ]
        action['context'] = {
            'default_move_type': 'out_invoice',
            'move_type': 'out_invoice',
            'journal_type': 'sale',
            'search_default_posted': 1,
        }
        return action
