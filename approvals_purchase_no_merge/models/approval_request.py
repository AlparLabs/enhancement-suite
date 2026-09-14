from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    create_new_rfq = fields.Boolean(
        string="Always Create New RFQ",
        default=False,
        help="When enabled, this approval generates its own separate RFQ(s) "
             "instead of merging lines into an existing draft RFQ for the same vendor.",
    )
