from odoo import models, api, _
from collections import defaultdict

class AccountPartnerGroupLedgerReportHandler(models.AbstractModel):
    _name = 'account.partner.group.ledger.report.handler'
    _inherit = 'account.partner.ledger.report.handler'
    _description = 'Partner Group Ledger Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        # 1. Fetch native partner lines using the parent logic
        partner_lines, totals_by_column_group = self._build_partner_lines(report, options)

        # 2. Extract all partner IDs and map them to their partner_group_id
        partner_ids = []
        for line in partner_lines:
            markup, model, record_id = report._parse_line_id(line['id'])[-1]
            if model == 'res.partner' and record_id:
                partner_ids.append(record_id)

        partners = self.env['res.partner'].with_context(active_test=False).browse(partner_ids)
        partner_to_group = {p.id: p.partner_group_id for p in partners}

        # 3. Group the partner lines
        lines_by_group = defaultdict(list)
        for line in partner_lines:
            markup, model, record_id = report._parse_line_id(line['id'])[-1]
            group = None
            if model == 'res.partner' and record_id:
                group = partner_to_group.get(record_id)
            lines_by_group[group].append(line)

        # 4. Construct the final hierarchical lines
        final_lines = []
        
        for group, p_lines in lines_by_group.items():
            if not group:
                group_name = _('Ungrouped Partners')
                group_line_id = report._get_generic_line_id('res.partner.group', None, markup='ungrouped')
            else:
                group_name = group.name
                group_line_id = report._get_generic_line_id('res.partner.group', group.id)

            # Sum columns across partners in this group
            group_columns = []
            for i, col in enumerate(options['columns']):
                col_sum = 0.0
                has_value = False
                for p_line in p_lines:
                    p_col = p_line['columns'][i]
                    # We look for 'no_format' value which holds the float value.
                    if p_col.get('no_format') is not None:
                        col_sum += p_col['no_format']
                        has_value = True

                if not has_value:
                    group_columns.append(report._build_column_dict(None, col, options=options))
                else:
                    group_columns.append(report._build_column_dict(col_sum, col, options=options))

            group_line = {
                'id': group_line_id,
                'name': group_name,
                'columns': group_columns,
                'level': 1,
                'unfoldable': False, # Keeps it fully expanded like a structural header
            }
            
            final_lines.append((0, group_line))

            # Add the partner lines directly under the group header
            for p_line in p_lines:
                p_line['level'] = 2
                p_line['parent_id'] = group_line_id
                final_lines.append((0, p_line))

        # 5. Inject sequence on dynamic lines
        # (This is handled because we append (0, dict) directly)

        # 6. Report total line
        final_lines.append((0, self._get_report_line_total(options, totals_by_column_group)))

        return final_lines

    def _report_expand_unfoldable_line_partner_ledger(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        # We intercept the move lines when a partner is expanded, and shift their level +1
        # so they visually indent under the Partner (which is now level 2 instead of 1)
        res = super()._report_expand_unfoldable_line_partner_ledger(
            line_dict_id, groupby, options, progress, offset, unfold_all_batch_data
        )
        for line in res.get('lines', []):
            if 'level' in line:
                line['level'] += 1
        return res
