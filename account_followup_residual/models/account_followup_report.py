from odoo import models, _
from odoo.tools.misc import formatLang


class AccountFollowupReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_followup_report_columns_name(self):
        columns = super()._get_followup_report_columns_name()
        columns.append({
            'name': _('Residual'),
            'class': 'number o_price_total',
            'style': 'text-align:center; white-space:nowrap;',
        })
        return columns

    def _get_followup_report_lines(self, options):
        lines = super()._get_followup_report_lines(options)

        aml_ids = [
            line['id'] for line in lines
            if line.get('type') in ('payment', 'unreconciled_aml')
        ]
        if not aml_ids:
            return lines

        amls_by_id = {
            aml.id: aml
            for aml in self.env['account.move.line'].browse(aml_ids)
        }
        company_currency = self.env.company.currency_id

        for line in lines:
            if line.get('type') in ('payment', 'unreconciled_aml'):
                aml = amls_by_id.get(line['id'])
                residual = aml.amount_residual if aml else 0.0
                line['columns'].append({
                    'name': formatLang(self.env, residual, currency_obj=company_currency),
                    'style': 'text-align:right; white-space:normal;',
                    'template': 'account_followup.line_template',
                    'no_format': residual,
                })
            else:
                # Total and separator lines need an empty cell to keep column alignment.
                line['columns'].append({'template': 'account_followup.line_template'})

        return lines
