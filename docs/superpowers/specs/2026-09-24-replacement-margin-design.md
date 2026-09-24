# Margen de reposición en el punto de venta

**Fecha:** 2026-09-24
**Actualizado a Adhoc:** 2026-09-24 — la parte de ventas la cubre Adhoc; este spec queda
sólo para POS.
**Módulo nuevo:** `alpardata_pos_replacement_margin` — depende de `point_of_sale` y
`alpardata_replenishment_cost` (punto 1, sobre Adhoc).
**Rama objetivo:** `19.0`
**Roadmap:** punto 5 (ver `2026-09-24-commercial-cost-roadmap.md`)

## Problema

El margen del POS se calcula con el costo contable (AVCO). Con inflación, vender por
encima del AVCO no garantiza poder **reponer** la mercadería: el margen contable da una
falsa sensación de ganancia. Hace falta ver también el **margen de reposición**.

## Ventas: se usa Adhoc

`product_replenishment_cost_sale_margin` (Adhoc, dependencia del punto 1) ya hace que el
costo de las líneas de pedido de venta sea el costo de reposición, y con eso el margen de
`sale_margin` pasa a ser de reposición en pedidos y en el análisis de ventas. No se
desarrolla nada propio para ventas.

Diferencia con el diseño original: en ventas se ve **un** margen (de reposición), no el
contable y el de reposición juntos.

## POS: `alpardata_pos_replacement_margin`

### Costo unitario

`product.product._pos_replenishment_cost(company, currency, date)`:
`replenishment_cost` del producto en `company` (Adhoc, con las reglas y la jerarquía del
punto 1); si es 0, `standard_price` (fallback); convertido de la moneda de la empresa a
`currency`. El costo se toma en la UoM del producto (las líneas de POS usan esa UoM).

### `pos.order.line`

| Campo | Tipo | Notas |
|---|---|---|
| `replacement_cost_unit` | Float | computado almacenado, `depends('product_id', 'order_id.company_id', 'order_id.currency_id')`: se fija al sincronizar la orden |
| `replacement_margin` | Monetary | computado almacenado, `price_subtotal − replacement_cost_unit × qty` (en devoluciones `qty` negativo → margen negativo) |

Productos combo → costo 0 (igual que el margen estándar del POS).

### `pos.order`

- `replacement_margin` (Monetary, computado almacenado, suma de líneas).

### `report.pos.order`

- `replacement_margin` en `_select`, con la misma conversión de moneda que `margin` en
  `point_of_sale/report/pos_order_report.py`.

### Vistas

- Orden POS: `replacement_margin` junto al margen; columnas opcionales en las líneas.
- Análisis de POS: medida "Margen de reposición" (los campos numéricos almacenados del
  reporte aparecen solos como medida).

No se modifica el frontend del POS (JS): el cálculo es 100 % backend.

## Migración de datos

Las órdenes anteriores a la instalación **no** se recalculan: quedarían con el costo de
hoy, que es justamente el dato engañoso. Un `pre_init_hook` crea las columnas con valor 0
antes de instalar, así el ORM no las recalcula. Se documenta en el README.

## Tests

1. Orden creada vía `sync_from_ui` → líneas con costo de reposición (lista con la regla
   del proveedor) y margen.
2. Devolución → margen negativo.
3. Producto sin costo de reposición → fallback AVCO.
4. `report.pos.order` expone `replacement_margin`.

## Decisiones

1. Ventas con el margen de Adhoc (reemplaza al contable en el pedido).
2. POS: módulo propio, costo fijado al sincronizar la orden, fallback a AVCO.
3. No se recalculan datos históricos al instalar.
4. Sin cambios en el frontend del POS.
