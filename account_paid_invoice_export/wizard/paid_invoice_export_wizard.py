import base64
import io
from datetime import datetime

import xlsxwriter

from odoo import fields, models, _
from odoo.exceptions import UserError

HEADERS = [
    'Factura',              # 0
    'Fecha de Factura',     # 1
    'Cliente',              # 2
    'Moneda',               # 3
    'Total',                # 4
    'Total en moneda',      # 5
    'Saldo Pendiente',      # 6
    'Equipo de Ventas',     # 7
    'Estado de Pago',       # 8
    'Pago Referencia',      # 9
    'Fecha de Pago',        # 10
    'Moneda Pago',          # 11
    'Monto Pagado',         # 12
    'Monto Aplicado (ARS)', # 13
    'Es Nota de Crédito',   # 14
]

# 0-based column indices for formatting
NUMERIC_COLS = {4, 5, 6, 12, 13}
DATE_COLS = {1, 10}


def _safe_field(record, field_name, default=''):
    """Return field value if it exists on the record, else default."""
    try:
        val = getattr(record, field_name, default)
        if val is False:
            return default
        return val
    except Exception:
        return default


class PaidInvoiceExportWizard(models.TransientModel):
    _name = 'paid.invoice.export.wizard'
    _description = 'Paid Invoice Excel Export'

    date_from = fields.Date(string='Fecha de Pago Desde')
    date_to = fields.Date(string='Fecha de Pago Hasta')
    company_ids = fields.Many2many(
        comodel_name='res.company',
        string='Empresas',
        default=lambda self: self.env.companies,
    )
    incl_paid = fields.Boolean(string='Pagada', default=True)
    incl_partial = fields.Boolean(string='Parcial', default=True)
    incl_in_payment = fields.Boolean(string='En proceso de pago', default=True)

    def _selected_payment_states(self):
        states = []
        if self.incl_paid:
            states.append('paid')
        if self.incl_partial:
            states.append('partial')
        if self.incl_in_payment:
            states.append('in_payment')
        return states

    def _get_invoice_domain(self):
        # Note: date_from / date_to filter by PAYMENT date, which lives on the
        # reconciliation, not on account.move. So the date range is applied
        # per-payment in _build_rows, not here in the search domain.
        states = self._selected_payment_states()
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', states),
        ]
        if self.company_ids:
            domain.append(('company_id', 'in', self.company_ids.ids))
        return domain

    def _invoice_partials(self, move):
        """Yield (partial, counterpart_move) for every reconciliation applied
        to the receivable lines of the invoice.

        Walks the invoice's receivable move lines and their partial
        reconciliations. For a customer invoice the invoice line is the debit,
        so the payment/credit-note shows up via matched_credit_ids; we also
        read matched_debit_ids defensively.
        """
        receivable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        for line in receivable_lines:
            for partial in line.matched_credit_ids:
                counterpart = partial.debit_move_id.move_id
                yield partial, counterpart
            for partial in line.matched_debit_ids:
                counterpart = partial.credit_move_id.move_id
                yield partial, counterpart

    @staticmethod
    def _as_datetime(value):
        """Convert a date to a datetime (for xlsx date formatting), or None."""
        return datetime.combine(value, datetime.min.time()) if value else None

    def _payment_date(self, partial, counterpart):
        """Effective payment date of a reconciliation."""
        return partial.max_date or counterpart.date

    def _payment_in_range(self, partial, counterpart):
        """True if the payment date falls within date_from / date_to."""
        pay_date = self._payment_date(partial, counterpart)
        if not pay_date:
            return False
        if self.date_from and pay_date < self.date_from:
            return False
        if self.date_to and pay_date > self.date_to:
            return False
        return True

    def _base_row(self, move):
        """Header-level columns shared by every row of an invoice (cols 0-8)."""
        currency_code = _safe_field(move, 'l10n_ar_currency_code', '') \
            or (move.currency_id.name or '')
        return [
            move.name or '',                                    # Factura
            self._as_datetime(move.invoice_date),               # Fecha de Factura
            move.partner_id.name or '',                         # Cliente
            currency_code,                                      # Moneda
            move.amount_total,                                  # Total
            move.amount_total_signed,                           # Total en moneda
            move.amount_residual,                               # Saldo Pendiente
            move.team_id.name if move.team_id else '',          # Equipo de Ventas
            move.payment_state or '',                           # Estado de Pago
        ]

    def _payment_row(self, move, partial, counterpart):
        """Full row (cols 0-14) for one applied payment."""
        pay_datetime = self._as_datetime(self._payment_date(partial, counterpart))
        is_refund = counterpart.move_type == 'out_refund'
        # 'Monto Pagado' is the full counterpart move total (mirrors the original
        # script): a payment split across several invoices repeats the whole
        # payment amount per invoice, while 'Monto Aplicado (ARS)' (partial.amount)
        # holds the per-invoice slice. Do not naively sum the 'Monto Pagado' column.
        return self._base_row(move) + [
            counterpart.ref or counterpart.name or '',          # Pago Referencia
            pay_datetime,                                       # Fecha de Pago
            counterpart.currency_id.name or '',                 # Moneda Pago
            counterpart.amount_total,                           # Monto Pagado
            partial.amount,                                     # Monto Aplicado (ARS)
            'Sí' if is_refund else 'No',                        # Es Nota de Crédito
        ]

    def _empty_payment_row(self, move):
        """Row for an invoice with no reconciliations (payment cols blank)."""
        return self._base_row(move) + [None, None, None, None, None, None]

    def _build_rows(self):
        moves = self.env['account.move'].search(
            self._get_invoice_domain(),
            order='invoice_date asc, name asc',
        )
        date_filter = bool(self.date_from or self.date_to)
        rows = []
        for move in moves:
            partials = list(self._invoice_partials(move))
            if date_filter:
                # Filtering by payment date: keep only payments in range and
                # drop invoices that have no payment inside the range (an
                # invoice with no reconciliation has no payment date).
                for partial, counterpart in partials:
                    if self._payment_in_range(partial, counterpart):
                        rows.append(self._payment_row(move, partial, counterpart))
            elif not partials:
                rows.append(self._empty_payment_row(move))
            else:
                for partial, counterpart in partials:
                    rows.append(self._payment_row(move, partial, counterpart))
        return rows

    def action_export(self):
        self.ensure_one()
        if not self._selected_payment_states():
            raise UserError(_('Seleccioná al menos un estado de pago.'))

        rows = self._build_rows()
        if not rows:
            raise UserError(_('No se encontraron registros con los filtros seleccionados.'))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Facturas Pagadas')

        fmt_header = workbook.add_format({
            'bold': True,
            'bg_color': '#1F4E79',
            'font_color': '#FFFFFF',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        fmt_date = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        fmt_number = workbook.add_format({'num_format': '#,##0.00'})
        fmt_text = workbook.add_format({'valign': 'vcenter'})

        worksheet.set_row(0, 30)
        for col, header in enumerate(HEADERS):
            worksheet.write(0, col, header, fmt_header)
            worksheet.set_column(col, col, 20)

        for row_idx, row in enumerate(rows, start=1):
            for col_idx, value in enumerate(row):
                if col_idx in DATE_COLS and isinstance(value, datetime):
                    worksheet.write_datetime(row_idx, col_idx, value, fmt_date)
                elif col_idx in NUMERIC_COLS and isinstance(value, (int, float)):
                    worksheet.write_number(row_idx, col_idx, value, fmt_number)
                else:
                    worksheet.write(row_idx, col_idx, value if value is not None else '', fmt_text)

        worksheet.autofilter(0, 0, len(rows), len(HEADERS) - 1)
        worksheet.freeze_panes(1, 0)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        filename = f"facturas_pagadas_{fields.Date.today()}.xlsx"
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
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
