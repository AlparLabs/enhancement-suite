from odoo import models, api, _

class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Override to conditionally hide the initial balance line.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['hide_initial_balance'] = previous_options.get('hide_initial_balance', True)