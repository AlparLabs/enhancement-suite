from odoo import models, _
from odoo.exceptions import UserError


FCE_DEBIT_CODES = {'201', '206', '211', '202', '207', '212'}
FCE_CREDIT_CODES = {'203', '208', '213'}

AMOUNT_COLUMNS = [
    'contado', 'cta_cte_nd', 'nc_contado', 'dev_ctacte_dia_ant',
    'nc_dev_ctacte_dia', 'fact_mipyme', 'nc_mipyme',
]
SUBTOTAL_KEYS = AMOUNT_COLUMNS + ['desct', 'cantidad_cc']

COLUMN_SPECS = [
    ('number', 'Comprobante'),
    ('partner_name', 'Cliente'),
    ('contado', 'Contado'),
    ('cta_cte_nd', 'Cta.Cte/ND'),
    ('nc_contado', 'N/C Cont.'),
    ('dev_ctacte_dia_ant', 'Dev.CtaCte D/Ant'),
    ('nc_dev_ctacte_dia', 'N/C Dev.CtaCte del Día'),
    ('fact_mipyme', 'Fact. MiPyme'),
    ('nc_mipyme', 'N/C MiPyme'),
    ('pct_desc', '% Desc'),
    ('desct', 'Desct.'),
    ('cantidad_cc', 'Cantid. CC'),
    ('lista', 'Lista'),
]


class ReportCashClosureVendor(models.AbstractModel):
    _name = 'report.sale_vendor_cash_closure.cash_closure_vendor'
    _description = 'Vendor Cash Closure Report'

    # -------------------------------------------------------------------------
    # Classification & per-move math
    # -------------------------------------------------------------------------

    def _classify_move(self, move):
        """Return the column key where this move's amount_total belongs."""
        doc_code = move.l10n_latam_document_type_id.code or ''
        if doc_code in FCE_CREDIT_CODES:
            return 'nc_mipyme'
        if doc_code in FCE_DEBIT_CODES:
            return 'fact_mipyme'

        is_ctacte = move.commercial_partner_id.use_partner_credit_limit
        is_refund = move.move_type == 'out_refund'
        if is_refund:
            return 'nc_dev_ctacte_dia' if is_ctacte else 'nc_contado'
        return 'cta_cte_nd' if is_ctacte else 'contado'

    def _compute_discount(self, move):
        """Return (weighted % discount, tax-inclusive discount amount)."""
        lines = move.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and l.product_id
        )
        gross_untaxed = sum(line.price_unit * line.quantity for line in lines)
        net_untaxed = sum(line.price_subtotal for line in lines)
        discount_untaxed = gross_untaxed - net_untaxed

        tax_factor = (move.amount_total / move.amount_untaxed) if move.amount_untaxed else 1.0
        discount_amount = discount_untaxed * tax_factor
        pct_desc = (discount_untaxed / gross_untaxed * 100) if gross_untaxed else 0.0
        return pct_desc, discount_amount

    def _move_amount_company_currency(self, move):
        """Convert amount_total to the company currency using the move's
        exchange rate. Same formula already used in this repo's
        account_invoice_line_export (invoice_currency_rate is the
        company->invoice-currency ratio, so we divide to go the other way).
        """
        if move.currency_id == move.company_currency_id or not move.invoice_currency_rate:
            return move.amount_total
        return move.amount_total / move.invoice_currency_rate

    # -------------------------------------------------------------------------
    # Vendor & pricelist resolution
    # -------------------------------------------------------------------------

    def _resolve_move_vendor(self, move, pos_order):
        """Return ((model, id) key, display name) for the move's salesperson.

        `counter_salesperson_id` comes from the pos_centralized_payment
        module (separate repo) and may not be installed — the field
        presence check keeps this working either way.
        """
        if pos_order and 'counter_salesperson_id' in pos_order._fields and pos_order.counter_salesperson_id:
            employee = pos_order.counter_salesperson_id
            return ('hr.employee', employee.id), employee.name
        if move.invoice_user_id:
            return ('res.users', move.invoice_user_id.id), move.invoice_user_id.name
        return (False, False), 'Sin vendedor'

    def _resolve_payment_vendor(self, payment):
        salesperson = payment.partner_id.user_id
        if salesperson:
            return ('res.users', salesperson.id), salesperson.name
        return (False, False), 'Sin vendedor'

    def _resolve_pricelist(self, move, pos_order):
        if pos_order and pos_order.pricelist_id:
            return pos_order.pricelist_id.name
        sale_orders = move.invoice_line_ids.sale_line_ids.mapped('order_id')
        if sale_orders and sale_orders[0].pricelist_id:
            return sale_orders[0].pricelist_id.name
        return ''

    # -------------------------------------------------------------------------
    # Row builders
    # -------------------------------------------------------------------------

    def _build_move_row(self, move):
        pos_order = self.env['pos.order'].search([('account_move', '=', move.id)], limit=1)
        column = self._classify_move(move)
        vendor_key, vendor_name = self._resolve_move_vendor(move, pos_order)
        pct_desc, discount_amount = self._compute_discount(move)

        row = {key: 0.0 for key in AMOUNT_COLUMNS}
        row[column] = self._move_amount_company_currency(move)
        row.update({
            'number': move.name or '',
            'partner_name': move.commercial_partner_id.name or '',
            'pct_desc': pct_desc,
            'desct': discount_amount,
            'cantidad_cc': 1.0 if column == 'cta_cte_nd' else 0.0,
            'lista': self._resolve_pricelist(move, pos_order),
        })
        return vendor_key, vendor_name, row

    def _build_payment_row(self, payment):
        vendor_key, vendor_name = self._resolve_payment_vendor(payment)

        row = {key: 0.0 for key in AMOUNT_COLUMNS}
        row['dev_ctacte_dia_ant'] = payment.amount
        row.update({
            'number': payment.name or payment.memo or '',
            'partner_name': payment.partner_id.name or '',
            'pct_desc': 0.0,
            'desct': 0.0,
            'cantidad_cc': 0.0,
            'lista': '',
        })
        return vendor_key, vendor_name, row

    # -------------------------------------------------------------------------
    # Aggregation
    # -------------------------------------------------------------------------

    def _compute_data(self, date, company):
        company = company or self.env.company
        moves = self.env['account.move'].search([
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('invoice_date', '=', date),
            ('company_id', '=', company.id),
        ], order='name asc')
        payments = self.env['account.payment'].search([
            ('partner_type', '=', 'customer'),
            ('payment_type', '=', 'inbound'),
            ('state', 'not in', ('draft', 'cancel')),
            ('date', '=', date),
            ('company_id', '=', company.id),
        ], order='name asc')

        if not moves and not payments:
            raise UserError(_('No se encontraron comprobantes ni cobranzas para el %s.') % date)

        groups = {}
        for move in moves:
            vendor_key, vendor_name, row = self._build_move_row(move)
            group = groups.setdefault(vendor_key, {'name': vendor_name, 'rows': []})
            group['rows'].append(row)
        for payment in payments:
            vendor_key, vendor_name, row = self._build_payment_row(payment)
            group = groups.setdefault(vendor_key, {'name': vendor_name, 'rows': []})
            group['rows'].append(row)

        group_list = []
        for key, group in groups.items():
            subtotal = {col: sum(r[col] for r in group['rows']) for col in SUBTOTAL_KEYS}
            group_list.append({
                'salesperson_name': group['name'],
                'is_unassigned': key == (False, False),
                'rows': group['rows'],
                'subtotal': subtotal,
            })
        group_list.sort(key=lambda g: (g['is_unassigned'], g['salesperson_name']))

        grand_total = {col: sum(g['subtotal'][col] for g in group_list) for col in SUBTOTAL_KEYS}

        return {
            'date': date,
            'company': company,
            'currency': company.currency_id,
            'groups': group_list,
            'grand_total': grand_total,
        }

    # -------------------------------------------------------------------------
    # QWeb entry point
    # -------------------------------------------------------------------------

    def _get_report_values(self, docids, data=None):
        wizards = self.env['cash.closure.report.wizard'].browse(docids)
        wizard = wizards[:1]
        report_data = self._compute_data(wizard.date, wizard.company_id)
        return {
            'doc_ids': docids,
            'doc_model': 'cash.closure.report.wizard',
            **report_data,
        }
