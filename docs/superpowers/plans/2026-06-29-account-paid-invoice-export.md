# Paid Invoice Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Odoo 18 module `account_paid_invoice_export` with a wizard that exports paid/partial customer invoices, one row per applied payment, to an `.xlsx` file — replacing the external `ExtraerFacutrasV2.py` JSON-RPC script.

**Architecture:** A `TransientModel` wizard (`paid.invoice.export.wizard`) takes basic filters (date range, companies, payment states), searches `account.move` via the ORM, walks each invoice's receivable-line reconciliations (`matched_debit_ids` / `matched_credit_ids` → `account.partial.reconcile`) to expand payments, builds rows with `xlsxwriter`, and returns the file as a downloadable `ir.attachment`. Follows the existing `account_invoice_line_export` module's conventions exactly.

**Tech Stack:** Odoo 18, Python, `xlsxwriter`, Odoo ORM, XML views. Module license `OEEL-1`.

---

## File Structure

```
account_paid_invoice_export/
├── __init__.py                                  # imports wizard package
├── __manifest__.py                              # module metadata
├── security/
│   └── ir.model.access.csv                      # wizard ACL for account groups
├── wizard/
│   ├── __init__.py                              # imports the wizard module
│   ├── paid_invoice_export_wizard.py            # the TransientModel + export logic
│   └── paid_invoice_export_wizard_views.xml     # form view + action + menuitem
└── tests/
    ├── __init__.py                              # imports test module
    └── test_paid_invoice_export.py              # TransactionCase tests
```

**Responsibilities:**
- `paid_invoice_export_wizard.py` — all wizard fields, domain building, payment expansion, and xlsx generation. Single file, matches the sibling module's single-file approach.
- `paid_invoice_export_wizard_views.xml` — form, `ir.actions.act_window`, and the `Accounting → Reporting` menu entry.
- `tests/test_paid_invoice_export.py` — Odoo `TransactionCase` exercising domain building, payment row expansion, and the no-results error, using in-test invoices + payments.

**Testing reality:** The rest of the repo ships no automated tests, and the full export depends on `l10n_ar` runtime data. We still add an Odoo `TransactionCase` for the logic that is testable without localization (domain, payment expansion against a posted invoice + payment, no-results `UserError`). The `l10n_ar_currency_code` column and the final byte-for-byte xlsx comparison against the script are verified manually (Task 8). Tests run with Odoo's test runner, not pytest.

---

## Task 1: Module scaffolding (manifest, init files)

**Files:**
- Create: `account_paid_invoice_export/__init__.py`
- Create: `account_paid_invoice_export/__manifest__.py`
- Create: `account_paid_invoice_export/wizard/__init__.py`

- [ ] **Step 1: Create root `__init__.py`**

`account_paid_invoice_export/__init__.py`:
```python
from . import wizard
```

- [ ] **Step 2: Create the manifest**

`account_paid_invoice_export/__manifest__.py`:
```python
{
    'name': 'Paid Invoice Export',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Export paid/partial customer invoices to Excel, one row per applied payment',
    'description': """
        Wizard to export customer invoices in payment_state paid / partial /
        in_payment, expanded one row per applied payment (with the amount
        applied in company currency, payment reference, date, and a credit-note
        flag). Replaces the external JSON-RPC extraction script.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/paid_invoice_export_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
```

- [ ] **Step 3: Create the wizard package `__init__.py`**

`account_paid_invoice_export/wizard/__init__.py`:
```python
from . import paid_invoice_export_wizard
```

- [ ] **Step 4: Commit**

```bash
git add account_paid_invoice_export/__init__.py account_paid_invoice_export/__manifest__.py account_paid_invoice_export/wizard/__init__.py
git commit -m "feat(paid_invoice_export): scaffold module manifest and init files"
```

---

## Task 2: Wizard model — fields and domain

**Files:**
- Create: `account_paid_invoice_export/wizard/paid_invoice_export_wizard.py`

- [ ] **Step 1: Create the wizard with fields and the domain helper**

`account_paid_invoice_export/wizard/paid_invoice_export_wizard.py`:
```python
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
```

Note: the spec left the payment-state filter form open; this plan uses three Booleans (simpler in the view than a Many2many-over-selection, identical behaviour). Default all `True` = the script's `['paid', 'partial', 'in_payment']`.

- [ ] **Step 2: Commit**

```bash
git add account_paid_invoice_export/wizard/paid_invoice_export_wizard.py
git commit -m "feat(paid_invoice_export): add wizard fields and invoice domain"
```

---

## Task 3: Payment expansion logic

**Files:**
- Modify: `account_paid_invoice_export/wizard/paid_invoice_export_wizard.py` (add methods to the class)

- [ ] **Step 1: Add the payment-expansion and row-building methods**

Append these methods inside the `PaidInvoiceExportWizard` class (after `_get_invoice_domain`):
```python
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

    def _base_row(self, move):
        """Header-level columns shared by every row of an invoice (cols 0-7)."""
        currency_code = _safe_field(move, 'l10n_ar_currency_code', '') \
            or (move.currency_id.name or '')
        return [
            move.name or '',                                    # Factura
            move.partner_id.name or '',                         # Cliente
            currency_code,                                      # Moneda
            move.amount_total,                                  # Total
            move.amount_total_signed,                           # Total en moneda
            move.amount_residual,                               # Saldo Pendiente
            move.team_id.name if move.team_id else '',          # Equipo de Ventas
            move.payment_state or '',                           # Estado de Pago
        ]

    def _payment_row(self, move, partial, counterpart):
        """Full row (cols 0-13) for one applied payment."""
        pay_date = partial.max_date or counterpart.date
        pay_datetime = (
            datetime.combine(pay_date, datetime.min.time())
            if pay_date else None
        )
        is_refund = counterpart.move_type == 'out_refund'
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
        rows = []
        for move in moves:
            partials = list(self._invoice_partials(move))
            if not partials:
                rows.append(self._empty_payment_row(move))
            else:
                for partial, counterpart in partials:
                    rows.append(self._payment_row(move, partial, counterpart))
        return rows
```

- [ ] **Step 2: Commit**

```bash
git add account_paid_invoice_export/wizard/paid_invoice_export_wizard.py
git commit -m "feat(paid_invoice_export): expand applied payments into rows"
```

---

## Task 4: Excel generation and download action

**Files:**
- Modify: `account_paid_invoice_export/wizard/paid_invoice_export_wizard.py` (add `action_export`)

- [ ] **Step 1: Add the `action_export` method**

Append inside the class (after `_build_rows`):
```python
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
```

- [ ] **Step 2: Commit**

```bash
git add account_paid_invoice_export/wizard/paid_invoice_export_wizard.py
git commit -m "feat(paid_invoice_export): generate xlsx and return download action"
```

---

## Task 5: Security, view, action, and menu

**Files:**
- Create: `account_paid_invoice_export/security/ir.model.access.csv`
- Create: `account_paid_invoice_export/wizard/paid_invoice_export_wizard_views.xml`

- [ ] **Step 1: Create the access CSV**

`account_paid_invoice_export/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_paid_invoice_export_wizard_user,paid.invoice.export.wizard user,model_paid_invoice_export_wizard,account.group_account_user,1,1,1,1
access_paid_invoice_export_wizard_manager,paid.invoice.export.wizard manager,model_paid_invoice_export_wizard,account.group_account_manager,1,1,1,1
```

- [ ] **Step 2: Verify the reporting menu parent xml id**

Run:
```bash
python -c "import odoo" 2>/dev/null; grep -rn "menu_finance_reports" $(python -c "import odoo, os; print(os.path.dirname(odoo.__file__))")/addons/account/views/ 2>/dev/null | head
```
Expected: a hit defining `menu_finance_reports` (the `Accounting → Reporting` root). If the environment can't locate Odoo source, confirm in the running instance that `account.menu_finance_reports` exists (Accounting app → Reporting menu). If the id differs in this install, use the id found here in Step 3's `parent` attribute.

- [ ] **Step 3: Create the view, action, and menu**

`account_paid_invoice_export/wizard/paid_invoice_export_wizard_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_paid_invoice_export_wizard_form" model="ir.ui.view">
        <field name="name">paid.invoice.export.wizard.form</field>
        <field name="model">paid.invoice.export.wizard</field>
        <field name="arch" type="xml">
            <form string="Exportar Facturas Pagadas">
                <group>
                    <group string="Filtros">
                        <field name="date_from"/>
                        <field name="date_to"/>
                        <field name="company_ids" widget="many2many_tags"/>
                    </group>
                    <group string="Estado de pago">
                        <field name="incl_paid"/>
                        <field name="incl_partial"/>
                        <field name="incl_in_payment"/>
                    </group>
                </group>
                <footer>
                    <button name="action_export"
                            string="Descargar Excel"
                            type="object"
                            class="btn-primary"/>
                    <button string="Cancelar"
                            class="btn-secondary"
                            special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="action_paid_invoice_export_wizard" model="ir.actions.act_window">
        <field name="name">Exportar Facturas Pagadas</field>
        <field name="res_model">paid.invoice.export.wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
    </record>

    <menuitem id="menu_paid_invoice_export"
              name="Exportar Facturas Pagadas"
              parent="account.menu_finance_reports"
              action="action_paid_invoice_export_wizard"
              sequence="99"/>

</odoo>
```

- [ ] **Step 4: Commit**

```bash
git add account_paid_invoice_export/security/ir.model.access.csv account_paid_invoice_export/wizard/paid_invoice_export_wizard_views.xml
git commit -m "feat(paid_invoice_export): add security, wizard view and reporting menu"
```

---

## Task 6: Tests — scaffolding and domain

**Files:**
- Create: `account_paid_invoice_export/tests/__init__.py`
- Create: `account_paid_invoice_export/tests/test_paid_invoice_export.py`

- [ ] **Step 1: Create the tests package**

`account_paid_invoice_export/tests/__init__.py`:
```python
from . import test_paid_invoice_export
```

- [ ] **Step 2: Write the failing domain test**

`account_paid_invoice_export/tests/test_paid_invoice_export.py`:
```python
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPaidInvoiceExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard = cls.env['paid.invoice.export.wizard'].create({})

    def test_domain_includes_selected_states_only(self):
        self.wizard.incl_paid = True
        self.wizard.incl_partial = False
        self.wizard.incl_in_payment = False
        domain = self.wizard._get_invoice_domain()
        self.assertIn(('move_type', '=', 'out_invoice'), domain)
        self.assertIn(('state', '=', 'posted'), domain)
        self.assertIn(('payment_state', 'in', ['paid']), domain)

    def test_no_states_selected_raises(self):
        from odoo.exceptions import UserError
        self.wizard.incl_paid = False
        self.wizard.incl_partial = False
        self.wizard.incl_in_payment = False
        with self.assertRaises(UserError):
            self.wizard.action_export()
```

- [ ] **Step 3: Run the tests to verify they pass once the module installs**

Run (adjust DB name / odoo-bin path to the environment):
```bash
odoo-bin -d <testdb> -i account_paid_invoice_export --test-enable --test-tags account_paid_invoice_export --stop-after-init
```
Expected: both tests PASS, module installs cleanly. If Odoo isn't runnable in this environment, note that and defer to Task 8 manual verification.

- [ ] **Step 4: Commit**

```bash
git add account_paid_invoice_export/tests/
git commit -m "test(paid_invoice_export): cover domain building and empty-state guard"
```

---

## Task 7: Tests — payment expansion against a real invoice + payment

**Files:**
- Modify: `account_paid_invoice_export/tests/test_paid_invoice_export.py`

- [ ] **Step 1: Add a test that posts an invoice, registers a payment, and checks rows**

Append this method to `TestPaidInvoiceExport`:
```python
    def test_paid_invoice_expands_to_payment_row(self):
        partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        product = self.env['product.product'].create({
            'name': 'Producto Test',
            'lst_price': 100.0,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': '2026-01-15',
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()

        # Register a full payment via the standard payment register wizard.
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({}).action_create_payments()

        self.assertEqual(invoice.payment_state, 'paid')

        self.wizard.incl_paid = True
        self.wizard.incl_partial = True
        self.wizard.incl_in_payment = True
        rows = self.wizard._build_rows()

        invoice_rows = [r for r in rows if r[0] == invoice.name]
        self.assertTrue(invoice_rows, 'invoice should appear in export rows')
        row = invoice_rows[0]
        self.assertEqual(row[1], 'Cliente Test')          # Cliente
        self.assertEqual(row[7], 'paid')                  # Estado de Pago
        self.assertIsNotNone(row[9])                      # Fecha de Pago set
        self.assertEqual(row[13], 'No')                   # Es Nota de Crédito
        self.assertAlmostEqual(row[12], 100.0, places=2)  # Monto Aplicado (ARS)
```

- [ ] **Step 2: Run the tests**

Run:
```bash
odoo-bin -d <testdb> -u account_paid_invoice_export --test-enable --test-tags account_paid_invoice_export --stop-after-init
```
Expected: all three tests PASS. If the company has no chart of accounts configured, the test DB must be created with `-i account` against a country/CoA; note any environment limitation and fall back to Task 8.

- [ ] **Step 3: Commit**

```bash
git add account_paid_invoice_export/tests/test_paid_invoice_export.py
git commit -m "test(paid_invoice_export): verify a paid invoice expands to a payment row"
```

---

## Task 8: Manual verification against the original script

**Files:** none (verification only)

- [ ] **Step 1: Install the module**

In the target Odoo instance (Falfersa or the client's DB): Apps → Update Apps List → search "Paid Invoice Export" → Install. Confirm no install errors in the log.

- [ ] **Step 2: Open the wizard**

Accounting → Reporting → "Exportar Facturas Pagadas". Confirm the form shows date range, company tags, and the three payment-state checkboxes (all checked by default).

- [ ] **Step 3: Download and compare**

With all defaults, click "Descargar Excel". Open the file and verify:
- Columns match exactly: Factura, Cliente, Moneda, Total, Total en moneda, Saldo Pendiente, Equipo de Ventas, Estado de Pago, Pago Referencia, Fecha de Pago, Moneda Pago, Monto Pagado, Monto Aplicado (ARS), Es Nota de Crédito.
- For a handful of known invoices, the number of rows per invoice equals the number of applied payments, and "Monto Aplicado (ARS)" matches what `ExtraerFacutrasV2.py` produced for the same invoices.
- An invoice with no reconciled payment shows one row with blank payment columns.
- A credit-note application shows "Sí" in "Es Nota de Crédito".

- [ ] **Step 4: Record the result**

Note in the PR description that manual verification passed (or list discrepancies to fix). Do not claim completion without this step's evidence.

---

## Self-Review Notes

- **Spec coverage:** module structure (Task 1), fields/filters incl. payment-state default (Task 2), payment expansion via ORM reconciliations + empty-payment row + refund flag (Task 3), xlsx styling + attachment download + no-results `UserError` (Task 4), security + reporting menu (Task 5), defensive `l10n_ar_currency_code` read (Task 3 `_base_row`), manual comparison vs script (Task 8). All 14 columns enumerated in Task 2 `HEADERS`.
- **Type/name consistency:** `_get_invoice_domain`, `_selected_payment_states`, `_invoice_partials`, `_base_row`, `_payment_row`, `_empty_payment_row`, `_build_rows`, `action_export` used consistently across Tasks 2–4 and the tests in 6–7. `HEADERS`, `NUMERIC_COLS`, `DATE_COLS` defined once in Task 2 and referenced in Task 4.
- **Open item carried from spec:** payment-state filter implemented as three Booleans (documented in Task 2).
```
