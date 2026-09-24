# Roadmap: costo comercial para retail en Argentina

**Fecha:** 2026-09-24
**Base existente:** `alpardata_purchase_reference_cost` (19.0.2.1.3) — separa costo
contable (AVCO) de costo comercial (`reference_cost`, lista del proveedor), con
vigencias, historial, programación, base de listas de precios y semáforo de divergencia.

## Puntos

| # | Tema | Módulo | Spec | Plan | Depende de |
|---|---|---|---|---|---|
| 1 | Costo de reposición desglosado | `alpardata_purchase_replacement_cost` | `2026-09-24-replacement-cost-design.md` | `plans/2026-09-24-replacement-cost.md` | base |
| 2 | Importador de listas de proveedores | `alpardata_supplier_pricelist_import` | `2026-09-24-supplier-pricelist-import-design.md` | `plans/2026-09-24-supplier-pricelist-import.md` | 1 |
| 3 | Margen erosionado y etiquetas pendientes | `alpardata_price_change_labels` | `2026-09-24-price-change-labels-design.md` | `plans/2026-09-24-price-change-labels.md` | 1, `product_label_3x8` |
| 4 | Cotización comercial (USD) — **opcional** | `alpardata_commercial_currency_rate` | `2026-09-24-commercial-currency-rate-design.md` | `plans/2026-09-24-commercial-currency-rate.md` | base (refactor del 1) |
| 5 | Margen de reposición en ventas/POS | `alpardata_sale_replacement_margin`, `alpardata_pos_replacement_margin` | `2026-09-24-replacement-margin-design.md` | `plans/2026-09-24-replacement-margin.md` | 1 |
| 6 | Promociones de proveedor (sell-in / sell-out) | `alpardata_supplier_promotion` | `2026-09-24-supplier-promotion-design.md` | `plans/2026-09-24-supplier-promotion.md` | 3, `sale`, `point_of_sale` |

## Orden de implementación

1 primero: todos dependen de él (fórmula, helper de conversión, hook de divergencia).
Después 2 → 3 → 6 → 5. 6 extiende el control de góndola del 3, así que va después.
2, 3 y 5 son independientes entre sí.

**4 es opcional**: sólo hace falta si el cliente tiene proveedores que cotizan en dólares y
quiere fijar precios con un dólar distinto del contable. Sin eso, el punto 1 ya convierte
con la cotización de Odoo. Si se hace, toca el módulo base: no correrlo en paralelo con
otro punto que también lo toque.

Una rama y un PR por punto, contra `19.0`.

## Decisión: no usar `product_replenishment_cost` de Adhoc

**Fecha:** 2026-09-24. **Contexto:** Adhoc tiene en `AlparLabs/product` (rama `19.0`)
`product_replenishment_cost` y módulos relacionados (`_sale_margin`, `_stock`,
`product_planned_price`), que se superponen con el punto 1 y con el módulo base
`alpardata_purchase_reference_cost`. Se evaluó reemplazar lo propio por Adhoc antes de
entrar en retail (FRAT).

**Decisión:** se sigue con el stack propio. No se reemplaza.

**Motivos** (verificados en el código de Adhoc 19.0):

| Necesidad (Broda la usa en producción) | Propio | Adhoc |
|---|---|---|
| Listas de proveedor con vigencia por fecha | Sí: el costo del producto toma sólo la ficha vigente; una ficha nueva cierra la anterior | No: `_compute_supplier_data` toma el primer proveedor por secuencia filtrando sólo por empresa, sin fechas. Una lista con fecha futura cambia el costo en el momento (sólo la OC respeta fechas, vía `_select_seller`) |
| Historial de cambios de lista por proveedor | Sí (`product.supplierinfo.cost.history`) | Sólo la fecha del último cambio (`last_date_price_updated`) |
| Programar cambios de costo a futuro | Sí (`product.cost.schedule`) | No |
| Listas de precios con base en el costo | Sí (bases "Costo de Referencia" y "Costo de Reposición") | No agrega base de lista: el precio va por precio planificado → `list_price` (asistente o cron) |
| Jerarquía sucursal → casa matriz | Sí | No (empresa o global) |

Migrar implicaría además convertir las listas cargadas (`reference_cost` → `price` + regla
por producto) y reconstruir encima de Adhoc casi todo lo que falta (puntos 2, 3, 5 POS
y 6).

**Qué se toma de Adhoc como idea:**

- Montos fijos en las reglas (flete por bulto): candidato a mejora del punto 1 si un
  cliente lo necesita.
- Su precio planificado confirma el enfoque de "Aplicar precio sugerido" (punto 3).

**Regla operativa:** no instalar `product_replenishment_cost` (ni los módulos que
dependen de él) en bases que usen `alpardata_purchase_reference_cost`. Los dos pisan el
cálculo de precio de la línea de compra
(`_compute_price_unit_and_date_planned_and_name` y `_prepare_purchase_order_line`).

**Revisar esta decisión si:** Adhoc agrega vigencias por fecha y base de listas de precios,
o si un cliente nuevo ya usa su stack y no necesita vigencias ni historial.

## Flujo de trabajo

1. Se implementa cada plan en Antigravity.
2. Se revisa y corrige en Claude Code (`/code-review` sobre la rama).
3. Se valida en una instancia (no hay instancia ejecutable local: tests en Odoo.sh o la
   instancia de desarrollo que corresponda).

## Deuda anotada

- El módulo base no aplica `reference_cost` como precio en las OC generadas por
  reabastecimiento (`_prepare_purchase_order_line`). Resuelto en parte en el punto 1
  (`a9ad041`): con bonificaciones en cascada, el reabastecimiento usa la lista.
- Resolver del proveedor calculado dos veces por producto (referencia y reposición):
  rendimiento, no correctitud.
