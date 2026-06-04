from odoo import models, fields


class AccountReport(models.Model):
    _inherit = 'account.report'

    filter_hide_initial_balance = fields.Boolean(
        string="Hide Initial Balances",
        compute=lambda x: x._compute_report_option_filter('filter_hide_initial_balance'),
        readonly=False,
        store=True,
        depends=['root_report_id', 'section_main_report_ids'],
    )
