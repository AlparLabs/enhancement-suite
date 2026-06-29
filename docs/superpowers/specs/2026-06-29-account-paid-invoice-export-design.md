# Diseño: `account_paid_invoice_export`

Fecha: 2026-06-29
Autor: Santiago Tojo (AlparData)

## Propósito

Wizard nativo en Odoo 18 que reemplaza el script externo `ExtraerFacutrasV2.py`
(JSON-RPC contra `falfersa.odoo.com`). Descarga facturas de cliente pagadas /
parciales, explotadas por pago aplicado, en un único archivo `.xlsx`. Dentro de
Odoo se usa el ORM directamente: no hay JSON-RPC, ni `.env`, ni `requests`.

Es funcionalidad para un cliente distinto al del módulo existente
`account_invoice_line_export`, por eso es un módulo separado. La granularidad
también es distinta: aquí cada fila es **un pago aplicado a una factura**, no una
línea de factura.

## Estructura del módulo

Sigue el patrón de `account_invoice_line_export`.

```
account_paid_invoice_export/
├── __init__.py
├── __manifest__.py
├── security/
│   └── ir.model.access.csv
└── wizard/
    ├── __init__.py
    ├── paid_invoice_export_wizard.py
    └── paid_invoice_export_wizard_views.xml
```

### `__manifest__.py`
- `name`: "Paid Invoice Export"
- `version`: `18.0.1.0.0`
- `category`: `Accounting/Accounting`
- `depends`: `['account']`
- `author`: AlparData
- `license`: `OEEL-1`
- `data`: `security/ir.model.access.csv`, `wizard/paid_invoice_export_wizard_views.xml`

### Seguridad
`ir.model.access.csv` da acceso de lectura/escritura/creación al wizard
(TransientModel) para el grupo `account.group_account_invoice`.

## Wizard `paid.invoice.export.wizard` (TransientModel)

### Campos / filtros
- `date_from` (Date, opcional) — filtra `invoice_date >=`.
- `date_to` (Date, opcional) — filtra `invoice_date <=`.
- `company_ids` (Many2many `res.company`, default `self.env.companies`).
- `payment_state` (Many2many sobre selection helper, default `paid`, `partial`,
  `in_payment`). Implementado como campo auxiliar; si Many2many sobre selection
  resulta incómodo, alternativa: tres campos Boolean (`incl_paid`,
  `incl_partial`, `incl_in_payment`) todos en `True` por default. El plan de
  implementación decide la forma concreta; el comportamiento es el mismo.

### `action_export()`
1. Construir dominio:
   - `move_type = 'out_invoice'`
   - `state = 'posted'`
   - `payment_state in (estados seleccionados)`
   - más `invoice_date` (desde/hasta) y `company_id in company_ids` si están.
2. `search` de `account.move` ordenado por `invoice_date asc, name asc`.
3. Por cada factura, obtener los pagos aplicados recorriendo las conciliaciones
   por ORM: las `account.move.line` cobrables de la factura
   (`line_ids` con cuenta tipo receivable) y sus `matched_debit_ids` /
   `matched_credit_ids` (`account.partial.reconcile`). De cada conciliación parcial:
   - referencia del pago (move/payment contrapartida: `ref` o `name`),
   - fecha del pago,
   - moneda del pago,
   - monto pagado,
   - monto aplicado en moneda compañía (ARS) = `partial.amount`,
   - flag "Es Nota de Crédito": la contrapartida es un `out_refund`.
4. Factura pagada sin conciliaciones → una fila con columnas de pago vacías
   (igual que el script con `invoice_payments_widget` vacío).
5. Generar `.xlsx` con `xlsxwriter`: header azul (`#1F4E79`, texto blanco,
   bordes, wrap), formato número `#,##0.00`, formato fecha `dd/mm/yyyy`,
   `autofilter` y `freeze_panes(1, 0)`.
6. Crear `ir.attachment` (binary) y devolver
   `ir.actions.act_url` a `/web/content/{id}?download=true`, `target: self`.

### Columnas (idénticas al script, una fila por pago)
1. Factura — `move.name`
2. Cliente — `move.partner_id.name`
3. Moneda — `move.l10n_ar_currency_code` (lectura defensiva) o `currency_id.name`
4. Total — `move.amount_total`
5. Total en moneda — `move.amount_total_signed`
6. Saldo Pendiente — `move.amount_residual`
7. Equipo de Ventas — `move.team_id.name`
8. Estado de Pago — `move.payment_state`
9. Pago Referencia — `ref`/`name` de la contrapartida
10. Fecha de Pago — fecha de la conciliación / pago
11. Moneda Pago — moneda del pago
12. Monto Pagado — monto del pago
13. Monto Aplicado (ARS) — `partial.amount` (moneda compañía)
14. Es Nota de Crédito — "Sí" / "No"

## Manejo de errores
- Sin resultados tras aplicar filtros → `UserError("No se encontraron registros
  con los filtros seleccionados.")`.
- `l10n_ar_currency_code` y cualquier campo de localización se leen vía helper
  `_safe_field` (mismo enfoque que `account_invoice_line_export`), para no
  romper si el campo no existe en alguna empresa/instalación.

## Menú
`Contabilidad → Informes`: entrada "Exportar Facturas Pagadas"
(`ir.actions.act_window` que abre el wizard en modo `new`).

## Testing / verificación
El repo no tiene tests automatizados y la lógica depende de datos de
localización argentina. La verificación es manual:
1. Instalar el módulo en una base con datos AR.
2. Abrir el wizard, aplicar filtros, descargar el `.xlsx`.
3. Comparar la salida contra `ExtraerFacutrasV2.py` sobre un conjunto de
   facturas conocido (mismos totales, mismas filas por pago, mismo
   "Monto Aplicado (ARS)").

## Fuera de alcance (YAGNI)
- CSV (solo Excel).
- Facturas de proveedor, notas de crédito como documento principal,
  recibos (solo `out_invoice`).
- Programación / envío automático del reporte.
```
