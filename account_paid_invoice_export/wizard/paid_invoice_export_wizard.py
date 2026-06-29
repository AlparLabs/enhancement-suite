import base64
import io
import logging
from datetime import datetime

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

HEADERS = [
    'Factura',              # 0
    'Cliente',              # 1
    'Moneda',               # 2
    'Total',                # 3
    'Total en moneda',      # 4
    'Saldo Pendiente',      # 5
    'Equipo de Ventas',     # 6
    'Estado de Pago',       # 7
    'Pago Referencia',      # 8
    'Fecha de Pago',        # 9
    'Moneda Pago',          # 10
    'Monto Pagado',         # 11
    'Monto Aplicado (ARS)', # 12
    'Es Nota de Crédito',   # 13
]

# 0-based column indices for formatting
NUMERIC_COLS = {3, 4, 5, 11, 12}
DATE_COLS = {9}


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

    date_from = fields.Date(string='Fecha Desde')
    date_to = fields.Date(string='Fecha Hasta')
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
        states = self._selected_payment_states()
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', states),
        ]
        if self.date_from:
            domain.append(('invoice_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_date', '<=', self.date_to))
        if self.company_ids:
            domain.append(('company_id', 'in', self.company_ids.ids))
        return domain

