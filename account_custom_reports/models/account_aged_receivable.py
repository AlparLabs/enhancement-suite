from odoo import models, api, _

class AccountAgedReceivableReportHandler(models.AbstractModel):
    _inherit = 'account.aged.receivable.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # Ensure we run the parent logic first (which handles hiding columns, etc.)
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        
        # Check if columns are already present to avoid duplicates
        column_labels = [col['expression_label'] for col in options['columns']]
        
        # Determine the column_group_key to attach new columns to.
        # Typically, string columns are attached to the first group or a default group.
        # We'll try to key off the first existing column or the first available group.
        default_group_key = options['columns'][0]['column_group_key'] if options.get('columns') else next(iter(options.get('column_groups', {})), 'default')

        # Append new columns
        # We add them with 'sortable': False to avoid SQL engine issues since we populate them post-process
        if 'salesperson' not in column_labels:
            options['columns'].append({
                'name': _('Salesperson'),
                'expression_label': 'salesperson',
                'figure_type': 'string',
                'sortable': False, 
                'column_group_key': default_group_key,
            })
            
        if 'sales_team' not in column_labels:
            options['columns'].append({
                'name': _('Sales Team'),
                'expression_label': 'sales_team',
                'figure_type': 'string',
                'sortable': False,
                'column_group_key': default_group_key,
            })

    def _custom_line_postprocessor(self, report, options, lines):
        # Run parent postprocessor first
        lines = super()._custom_line_postprocessor(report, options, lines)
        
        # Find indices of our custom columns in the current options
        col_indices = {}
        for index, col in enumerate(options['columns']):
            if col['expression_label'] in ('salesperson', 'sales_team'):
                col_indices[col['expression_label']] = index
                
        # If columns are not found (e.g. somehow filtered out), do nothing
        if not col_indices:
            return lines

        # 1. Collect IDs to fetch data in batch
        partner_ids = set()
        move_line_ids = set()
        
        for line in lines:
            model, res_id = report._get_model_info_from_id(line['id'])
            if model == 'res.partner':
                partner_ids.add(res_id)
            elif model == 'account.move.line':
                move_line_ids.add(res_id)
        
        # 2. Fetch Data
        partners_data = {}
        if partner_ids:
            partners = self.env['res.partner'].browse(list(partner_ids))
            for p in partners:
                partners_data[p.id] = {
                    'salesperson': p.user_id.name or '',
                    'sales_team': p.team_id.name or ''
                }
                
        moves_data = {}
        if move_line_ids:
            # For move lines, we want the info from the related Move (Invoice)
            amls = self.env['account.move.line'].browse(list(move_line_ids))
            for aml in amls:
                moves_data[aml.id] = {
                    'salesperson': aml.move_id.invoice_user_id.name or '',
                    'sales_team': aml.move_id.team_id.name or ''
                }

        # 3. Populate Lines
        for line in lines:
            model, res_id = report._get_model_info_from_id(line['id'])
            data = {}
            
            if model == 'res.partner':
                data = partners_data.get(res_id, {})
            elif model == 'account.move.line':
                data = moves_data.get(res_id, {})
            
            # Fill the columns
            for label, index in col_indices.items():
                if label in data:
                    # Defensive check: ensure the line has enough columns
                    # (Standard lines should match options['columns'] length)
                    if index < len(line['columns']):
                        line['columns'][index]['name'] = data[label]
                        line['columns'][index]['no_format'] = data[label] # Useful for exports
                        
        return lines
