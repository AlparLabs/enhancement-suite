# Account Custom Reports

Este módulo introduce personalizaciones específicas para los reportes contables de Odoo (requiere `account_reports`).

## Funcionalidades principales

### 1. Ocultar Saldos Iniciales
Modifica los reportes de **Libro Mayor** (General Ledger) y **Libro de Empresa** (Partner Ledger) para ocultar las líneas de saldos iniciales:
- En el reporte de *Libro de Empresa* (`account.partner.ledger.report.handler`), fuerza la opción `hide_initial_balance = True`.
- En el reporte de *Libro Mayor* (`account.general.ledger.report.handler`), implementa la misma opción y ajusta la generación dinámica de líneas y los cálculos de balances para excluir los montos provenientes de periodos anteriores, mostrando únicamente los movimientos del periodo seleccionado.

### 2. Nuevas columnas en Cuentas por Cobrar
Añade dos columnas adicionales al reporte de **Cuentas por cobrar vencidas** (Aged Receivable / `account.aged.receivable.report.handler`):
- **Vendedor (Salesperson):** Obtenido del usuario asignado al contacto (`res.partner.user_id`) o del vendedor asignado a la factura (`account.move.invoice_user_id`).
- **Equipo de Ventas (Sales Team):** Obtenido del equipo asignado al contacto (`res.partner.x_studio_equipo_de_ventas`) o del equipo asignado a la factura (`account.move.team_id`).

## Dependencias
- `account_reports`

## Autor
- AlparData (https://www.alpardata.com.ar)
