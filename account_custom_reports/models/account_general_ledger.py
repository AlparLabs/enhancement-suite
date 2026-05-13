# -*- coding: utf-8 -*-
from odoo import models, fields

class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Override to conditionally hide the initial balance line.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['hide_initial_balance'] = previous_options.get('hide_initial_balance', True)

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        if not options.get('hide_initial_balance'):
            return super()._dynamic_lines_generator(report, options, all_column_groups_expression_totals, warnings=warnings)

        from collections import defaultdict
        lines = []
        date_from = fields.Date.from_string(options['date']['date_from'])
        company_currency = self.env.company.currency_id

        totals_by_column_group = defaultdict(lambda: {'debit': 0, 'credit': 0, 'balance': 0})
        for account, column_group_results in self._query_values(report, options):
            eval_dict = {}
            has_lines = False
            for column_group_key, results in column_group_results.items():
                account_sum = results.get('sum', {})
                initial_balance = results.get('initial_balance', {})
                # Note: Unaffected earnings typically belong to past periods. When hiding initial balances
                # logically we also hide the accumulated unaffected earnings to only show the period's data.

                account_debit = account_sum.get('debit', 0.0) - initial_balance.get('debit', 0.0)
                account_credit = account_sum.get('credit', 0.0) - initial_balance.get('credit', 0.0)
                account_balance = account_sum.get('balance', 0.0) - initial_balance.get('balance', 0.0)
                amount_currency = account_sum.get('amount_currency', 0.0) - initial_balance.get('amount_currency', 0.0)

                eval_dict[column_group_key] = {
                    'amount_currency': amount_currency,
                    'debit': account_debit,
                    'credit': account_credit,
                    'balance': account_balance,
                }

                max_date = account_sum.get('max_date')
                has_lines = has_lines or (max_date and max_date >= date_from)

                totals_by_column_group[column_group_key]['debit'] += account_debit
                totals_by_column_group[column_group_key]['credit'] += account_credit
                totals_by_column_group[column_group_key]['balance'] += account_balance

            # If hiding initial balances, skip accounts that have no lines and 0 balances in the period
            has_movements = any(
                company_currency.compare_amounts(ev.get('debit', 0.0), 0.0) != 0 or 
                company_currency.compare_amounts(ev.get('credit', 0.0), 0.0) != 0 or
                company_currency.compare_amounts(ev.get('balance', 0.0), 0.0) != 0
                for ev in eval_dict.values()
            )
            
            if not has_lines and not has_movements:
                continue

            lines.append(self._get_account_title_line(report, options, account, has_lines, eval_dict))

        # Report total line.
        for totals in totals_by_column_group.values():
            totals['balance'] = company_currency.round(totals['balance'])

        # Tax Declaration lines.
        journal_options = report._get_options_journals(options)
        if len(options['column_groups']) == 1 and len(journal_options) == 1 and journal_options[0]['type'] in ('sale', 'purchase'):
            lines += self._tax_declaration_lines(report, options, journal_options[0]['type'])

        # Total line
        lines.append(self._get_total_line(report, options, totals_by_column_group))

        # Odoo 16/17 tuple format for report lines uses (0, line)
        return [(0, line) for line in lines]

    def _get_initial_balance_values(self, report, account_ids, options):
        res = super()._get_initial_balance_values(report, account_ids, options)
        if options.get('hide_initial_balance'):
            for account_id in res:
                account, init_bal_dict = res[account_id]
                for col_group_key in init_bal_dict:
                    init_bal_dict[col_group_key] = {
                        'debit': 0.0,
                        'credit': 0.0,
                        'balance': 0.0,
                        'amount_currency': 0.0,
                    }
        return res

    def _report_expand_unfoldable_line_general_ledger(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        if not options.get('hide_initial_balance'):
            return super()._report_expand_unfoldable_line_general_ledger(line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=unfold_all_batch_data)

        def init_load_more_progress(line_dict):
            return {
                column['column_group_key']: line_col.get('no_format', 0)
                for column, line_col in zip(options['columns'], line_dict['columns'])
                if column['expression_label'] == 'balance'
            }

        report = self.env.ref('account_reports.general_ledger_report')
        model, model_id = report._get_model_info_from_id(line_dict_id)

        lines = []

        # We skip the initial balance line completely. Compute a 0-progress for first expansion.
        if offset == 0:
            progress = {
                column['column_group_key']: 0.0
                for column in options['columns']
                if column['expression_label'] == 'balance'
            }

        limit_to_load = report.load_more_limit + 1 if getattr(report, 'load_more_limit', None) and options.get('export_mode') != 'print' else None
        if unfold_all_batch_data:
            aml_results = unfold_all_batch_data['aml_results'][model_id]
            has_more = unfold_all_batch_data['has_more'].get(model_id, False)
        else:
            aml_results, has_more = self._get_aml_values(report, options, [model_id], offset=offset, limit=limit_to_load)
            aml_results = aml_results[model_id]

        next_progress = progress
        for aml_result in aml_results.values():
            new_line = self._get_aml_line(report, line_dict_id, options, aml_result, next_progress)
            lines.append(new_line)
            next_progress = init_load_more_progress(new_line)

        return {
            'lines': lines,
            'offset_increment': getattr(report, 'load_more_limit', 0) or 0,
            'has_more': has_more,
            'progress': next_progress,
        }
