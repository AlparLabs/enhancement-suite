import base64
import io

import xlsxwriter

from odoo import fields, models

from ..report.report_cash_closure_vendor import COLUMN_SPECS, SUBTOTAL_KEYS


class CashClosureReportWizard(models.TransientModel):
    _name = 'cash.closure.report.wizard'
    _description = 'Vendor Cash Closure Report Wizard'

    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
    )

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('sale_vendor_cash_closure.action_report_cash_closure_vendor').report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        report_data = self.env['report.sale_vendor_cash_closure.cash_closure_vendor']._compute_data(
            self.date, self.company_id
        )
        return self._build_xlsx_attachment(report_data)

    def _build_xlsx_attachment(self, report_data):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Cierre de Caja')

        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#1F4E79', 'font_color': '#FFFFFF', 'border': 1})
        fmt_group = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2'})
        fmt_subtotal = workbook.add_format({'bold': True, 'top': 1})
        fmt_number = workbook.add_format({'num_format': '#,##0.00'})
        fmt_subtotal_number = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'top': 1})

        col_count = len(COLUMN_SPECS)
        for col, (_key, label) in enumerate(COLUMN_SPECS):
            worksheet.write(0, col, label, fmt_header)
            worksheet.set_column(col, col, 16)

        row_idx = 1
        for group in report_data['groups']:
            worksheet.merge_range(
                row_idx, 0, row_idx, col_count - 1,
                "Vendedor: %s" % group['salesperson_name'], fmt_group,
            )
            row_idx += 1
            for row in group['rows']:
                for col, (key, _label) in enumerate(COLUMN_SPECS):
                    value = row[key]
                    if key in SUBTOTAL_KEYS or key == 'pct_desc':
                        worksheet.write_number(row_idx, col, value, fmt_number)
                    else:
                        worksheet.write(row_idx, col, value or '')
                row_idx += 1

            worksheet.write(row_idx, 0, 'Subtotal', fmt_subtotal)
            worksheet.write_blank(row_idx, 1, None, fmt_subtotal)
            for col, (key, _label) in enumerate(COLUMN_SPECS):
                if col < 2:
                    continue
                if key in SUBTOTAL_KEYS:
                    worksheet.write_number(row_idx, col, group['subtotal'].get(key, 0.0), fmt_subtotal_number)
                else:
                    worksheet.write_blank(row_idx, col, None, fmt_subtotal)
            row_idx += 2

        worksheet.write(row_idx, 0, 'Total General', fmt_subtotal)
        worksheet.write_blank(row_idx, 1, None, fmt_subtotal)
        for col, (key, _label) in enumerate(COLUMN_SPECS):
            if col < 2:
                continue
            if key in SUBTOTAL_KEYS:
                worksheet.write_number(row_idx, col, report_data['grand_total'].get(key, 0.0), fmt_subtotal_number)
            else:
                worksheet.write_blank(row_idx, col, None, fmt_subtotal)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        filename = "cierre_caja_%s.xlsx" % self.date
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
