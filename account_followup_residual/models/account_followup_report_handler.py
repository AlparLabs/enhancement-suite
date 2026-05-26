from odoo import models


class AccountFollowupCustomHandler(models.AbstractModel):
    _inherit = 'account.followup.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        # Exclude move lines belonging to fully paid or reversed invoices so they
        # don't appear as outstanding in the UI Follow-Up Report.
        options['forced_domain'] = options.get('forced_domain', []) + [
            ('move_id.payment_state', 'not in', ('paid', 'reversed')),
        ]
