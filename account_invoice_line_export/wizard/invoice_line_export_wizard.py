import base64
import io
import logging
from datetime import datetime

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MOVE_TYPE_LABELS = {
    'out_invoice': 'Factura de Cliente',
    'out_refund': 'Nota de Crédito Cliente',
    'in_invoice': 'Factura de Proveedor',
    'in_refund': 'Nota de Crédito Proveedor',
}

HEADERS = [
    'SUC',
    'OV',
    'PipeDrive ID',
    'TIPO DE DOCUMENTO',
    'NRO DE DOC',
    'FECHA DE DOCUMENTO DE VENTA',
    'DIARIO',
    'CUENTA CONTABLE',
    'CLIENTE',
    'TAX ID',
    'TIPO DE CLIENTE',
    'PROVINCIA DE ENTREGA',
    'PROVINCIA DEL CLIENTE',
    'EQUIPO DE VENTAS',
    'LISTA DE PRECIOS',
    'PRODUCTO',
    'CATEGORÍA DE PRODUCTOS',
    'CANTIDAD',
    'Pr unitario neto',
    'Descuento',
    'VALOR NETO',
    'VALOR BRUTO',
    'MONEDA',
    'TASA DE CAMBIO',
]

# Column indices for numeric formatting (0-based, EMPRESA removed so all shift -1)
NUMERIC_COLS = {17, 18, 19, 20, 21, 23}  # CANTIDAD, Pr unitario neto, Descuento, VALOR NETO, VALOR BRUTO, TASA DE CAMBIO
DATE_COLS = {5}  # FECHA DE DOCUMENTO DE VENTA


def _safe_field(record, field_name, default=''):
    """Return field value if it exists on the record, else default."""
    try:
        val = getattr(record, field_name, default)
        if val is False:
            return default
        return val
    except Exception:
        return default


def _many2one_name(record, field_name):
    """Return the name of a Many2one field, or '' if missing/unset."""
    try:
        rel = getattr(record, field_name, False)
        if rel and hasattr(rel, 'name'):
            return rel.name or ''
        return ''
    except Exception:
        return ''


class InvoiceLineExportWizard(models.TransientModel):
    _name = 'invoice.line.export.wizard'
    _description = 'Invoice / Sale Line Flat Export'

    report_type = fields.Selection(
        selection=[
            ('customer_invoice', 'Facturas de Clientes'),
            ('vendor_bill', 'Facturas de Proveedores'),
            ('sale', 'Ventas'),
        ],
        string='Tipo de Exportación',
        required=True,
        default='customer_invoice',
    )
    date_from = fields.Date(string='Fecha Desde')
    date_to = fields.Date(string='Fecha Hasta')
    company_ids = fields.Many2many(
        comodel_name='res.company',
        string='Empresas',
        default=lambda self: self.env.companies,
    )
    invoice_state = fields.Selection(
        selection=[
            ('posted', 'Publicado'),
            ('draft', 'Borrador'),
            ('all', 'Todos'),
        ],
        string='Estado',
        default='posted',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Auto-detect type from the action context
        ctx_type = self.env.context.get('default_report_type')
        if ctx_type:
            res['report_type'] = ctx_type
        return res

    # -------------------------------------------------------------------------
    # Main export entry point
    # -------------------------------------------------------------------------

    def action_export(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Exportación')

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

        if self.report_type in ('customer_invoice', 'vendor_bill'):
            rows = self._get_invoice_rows()
        else:
            rows = self._get_sale_rows()

        if not rows:
            raise UserError(_('No se encontraron registros con los filtros seleccionados.'))

        for row_idx, row in enumerate(rows, start=1):
            for col_idx, value in enumerate(row):
                if col_idx in DATE_COLS and isinstance(value, datetime):
                    worksheet.write_datetime(row_idx, col_idx, value, fmt_date)
                elif col_idx in NUMERIC_COLS and isinstance(value, (int, float)):
                    worksheet.write_number(row_idx, col_idx, value, fmt_number)
                else:
                    worksheet.write(row_idx, col_idx, value if value is not None else '', fmt_text)

        last_row = len(rows)
        worksheet.autofilter(0, 0, last_row, len(HEADERS) - 1)
        worksheet.freeze_panes(1, 0)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        report_labels = dict(self._fields['report_type'].selection)
        label = report_labels.get(self.report_type, self.report_type)
        filename = f"exportacion_{label}_{fields.Date.today()}.xlsx".replace(' ', '_')

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

    # -------------------------------------------------------------------------
    # Invoice rows (customer & vendor)
    # -------------------------------------------------------------------------

    def _get_invoice_domain(self):
        if self.report_type == 'customer_invoice':
            move_types = ['out_invoice', 'out_refund']
        else:
            move_types = ['in_invoice', 'in_refund']

        domain = [
            ('move_type', 'in', move_types),
            ('state', '!=', 'cancel'),
        ]
        if self.invoice_state != 'all':
            domain.append(('state', '=', self.invoice_state))
        if self.date_from:
            domain.append(('invoice_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_date', '<=', self.date_to))
        if self.company_ids:
            domain.append(('company_id', 'in', self.company_ids.ids))
        return domain

    def _get_invoice_rows(self):
        moves = self.env['account.move'].search(
            self._get_invoice_domain(),
            order='invoice_date asc, name asc',
        )
        rows = []
        for move in moves:
            # Credit notes → negative sign on quantities and amounts
            sign = -1 if move.move_type in ('out_refund', 'in_refund') else 1

            suc = move.company_id.name
            partner = move.partner_id
            delivery = move.partner_shipping_id

            tipo_cliente = self._resolve_tipo_cliente(partner)
            sales_team = move.team_id.name if move.team_id else _many2one_name(partner, 'x_studio_equipo_de_ventas')

            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note') and l.product_id
            )

            for line in product_lines:
                ov, pipedrive_id, pricelist = self._extract_sale_order_data(line, move)

                invoice_date = (
                    datetime.combine(move.invoice_date, datetime.min.time())
                    if move.invoice_date else None
                )

                account_label = ''
                if line.account_id:
                    account_label = f"{line.account_id.code} {line.account_id.name}".strip()

                rows.append([
                    suc,                                                        # SUC
                    ov,                                                         # OV
                    pipedrive_id,                                               # PipeDrive ID
                    MOVE_TYPE_LABELS.get(move.move_type, move.move_type),       # TIPO DE DOCUMENTO
                    move.name,                                                  # NRO DE DOC
                    invoice_date,                                               # FECHA DE DOCUMENTO DE VENTA
                    move.journal_id.name,                                       # DIARIO
                    account_label,                                              # CUENTA CONTABLE
                    partner.name or '',                                         # CLIENTE
                    partner.vat or '',                                          # TAX ID
                    tipo_cliente,                                               # TIPO DE CLIENTE
                    delivery.state_id.name if delivery else '',                 # PROVINCIA DE ENTREGA
                    partner.state_id.name or '',                                # PROVINCIA DEL CLIENTE
                    sales_team,                                                 # EQUIPO DE VENTAS
                    pricelist,                                                  # LISTA DE PRECIOS
                    line.product_id.name or '',                                 # PRODUCTO
                    line.product_id.categ_id.complete_name or '',               # CATEGORÍA DE PRODUCTOS
                    sign * line.quantity,                                       # CANTIDAD
                    abs(line.price_unit),                                       # Pr unitario neto
                    abs(line.discount),                                         # Descuento
                    sign * line.price_subtotal,                                 # VALOR NETO
                    sign * line.price_total,                                    # VALOR BRUTO
                    move.currency_id.name,                                      # MONEDA
                    move.invoice_currency_rate or 1.0,                          # TASA DE CAMBIO
                ])

        return rows

    # -------------------------------------------------------------------------
    # Sale order rows
    # -------------------------------------------------------------------------

    def _get_sale_domain(self):
        domain = [('state', 'not in', ['draft', 'cancel'])]
        if self.date_from:
            domain.append(('date_order', '>=', str(self.date_from) + ' 00:00:00'))
        if self.date_to:
            domain.append(('date_order', '<=', str(self.date_to) + ' 23:59:59'))
        if self.company_ids:
            domain.append(('company_id', 'in', self.company_ids.ids))
        return domain

    def _get_sale_rows(self):
        orders = self.env['sale.order'].search(
            self._get_sale_domain(),
            order='date_order asc, name asc',
        )
        rows = []
        for order in orders:
            suc = order.company_id.name
            partner = order.partner_id
            delivery = order.partner_shipping_id
            pipedrive_id = _safe_field(order, 'x_studio_pipedrive_id') or ''
            pricelist = order.pricelist_id.name if order.pricelist_id else ''
            tipo_cliente = self._resolve_tipo_cliente(partner)
            sales_team = order.team_id.name if order.team_id else ''

            order_date = order.date_order.replace(hour=0, minute=0, second=0, microsecond=0) if order.date_order else None

            product_lines = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id
            )

            for line in product_lines:
                rows.append([
                    suc,                                        # SUC
                    order.name,                                 # OV
                    pipedrive_id,                               # PipeDrive ID
                    'Venta',                                    # TIPO DE DOCUMENTO
                    order.name,                                 # NRO DE DOC
                    order_date,                                 # FECHA DE DOCUMENTO DE VENTA
                    '',                                         # DIARIO
                    '',                                         # CUENTA CONTABLE
                    partner.name or '',                         # CLIENTE
                    partner.vat or '',                          # TAX ID
                    tipo_cliente,                               # TIPO DE CLIENTE
                    delivery.state_id.name if delivery else '', # PROVINCIA DE ENTREGA
                    partner.state_id.name or '',                # PROVINCIA DEL CLIENTE
                    sales_team,                                 # EQUIPO DE VENTAS
                    pricelist,                                  # LISTA DE PRECIOS
                    line.product_id.name or '',                 # PRODUCTO
                    line.product_id.categ_id.complete_name or '', # CATEGORÍA DE PRODUCTOS
                    line.product_uom_qty,                       # CANTIDAD
                    abs(line.price_unit),                       # Pr unitario neto
                    abs(line.discount),                         # Descuento
                    line.price_subtotal,                        # VALOR NETO
                    line.price_total,                           # VALOR BRUTO
                    order.currency_id.name,                     # MONEDA
                    1.0,                                        # TASA DE CAMBIO (not stored on sale order)
                ])

        return rows

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _extract_sale_order_data(self, line, move):
        """Return (ov, pipedrive_id, pricelist) strings from linked sale orders."""
        sale_orders = line.sale_line_ids.mapped('order_id') if line.sale_line_ids else self.env['sale.order']

        if sale_orders:
            ov = ', '.join(sale_orders.mapped('name'))
            pipedrive_ids = list(filter(None, [
                _safe_field(o, 'x_studio_pipedrive_id') for o in sale_orders
            ]))
            pipedrive_id = ', '.join(str(p) for p in pipedrive_ids)
            pricelists = [o.pricelist_id.name for o in sale_orders if o.pricelist_id]
            pricelist = ', '.join(dict.fromkeys(pricelists))  # deduplicate, preserve order
        else:
            ov = move.invoice_origin or ''
            pipedrive_id = ''
            pricelist = ''

        return ov, pipedrive_id, pricelist

    def _resolve_tipo_cliente(self, partner):
        """Resolve TIPO DE CLIENTE from partner Studio field (char or many2one)."""
        val = _safe_field(partner, 'x_studio_tipo_cliente', False)
        if val is False or val == '':
            return ''
        if hasattr(val, 'name'):
            return val.name or ''
        return str(val)
