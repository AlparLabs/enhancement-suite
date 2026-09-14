from odoo import models


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Override to force hiding the initial balance line.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['hide_initial_balance'] = True

    def _get_query(self, options, current_groupby, order_by_account=False, offset=0, limit=None):
        if options.get('hide_initial_balance') and options.get('date', {}).get('date_from'):
            options = {
                **options,
                'forced_domain': options.get('forced_domain', []) + [('date', '>=', options['date']['date_from'])],
            }
        return super()._get_query(options, current_groupby, order_by_account=order_by_account, offset=offset, limit=limit)
