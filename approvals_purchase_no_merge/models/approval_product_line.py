from odoo import models


class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    def _get_purchase_orders_domain(self, vendor):
        domain = super()._get_purchase_orders_domain(vendor)
        if self.approval_request_id.create_new_rfq:
            domain += [('origin', '=', self.approval_request_id.name)]
        return domain
