# Margen erosionado y cola de etiquetas pendientes

**Fecha:** 2026-09-24
**Módulo nuevo:** `alpardata_price_change_labels`
**Depende de:** `alpardata_replenishment_cost` (punto 1, sobre Adhoc), `product_label_3x8`
**Actualizado a Adhoc:** 2026-09-24 — costo = `replenishment_cost` de Adhoc; recargo
objetivo = `sale_margin` (margen por categoría del punto 1); el precio sugerido es el
precio planificado de Adhoc.
**Rama objetivo:** `19.0`
**Roadmap:** punto 3 (ver `2026-09-24-commercial-cost-roadmap.md`)

## Problema

Con inflación, lo que importa es cuánto tarda un aumento de costo en llegar a la góndola:

1. Si el precio de venta es fijo (`list_price` o regla de precio fijo), un aumento de
   costo **erosiona el margen** sin que nadie se entere.
2. Si el precio se calcula desde el costo (precio planificado "por margen" de Adhoc), el
   precio cambia al actualizarlo, pero **la etiqueta de la góndola queda vieja**. En Argentina el
   precio exhibido es obligatorio (Res. 4/2025, Ley 27.743, ya contemplados en
   `product_label_3x8`).

## Objetivo

- Detectar productos cuyo margen sobre reposición quedó por debajo del objetivo.
- Mantener una **cola de etiquetas pendientes**: productos cuyo precio de góndola actual
  difiere del último impreso, sin importar la causa (costo, cotización, regla de lista,
  cambio manual).

## Definiciones

- **Lista de góndola**: `res.company.shelf_pricelist_id` (Ajustes → Compras, bloque
  "Góndola"). Si está vacía, se usa `list_price`.
- **Precio de góndola** (`shelf_price`): el `price_final` que calcula
  `report.product_label_3x8.report_producttemplatelabel3x8._get_label_info(product,
  pricelist)` sin promoción. Es **la misma función que imprime la etiqueta**: lo que se
  controla es exactamente lo que se imprime.
- **Precio de góndola sin impuestos** (`shelf_price_untaxed`): el `price_net` de esa
  misma función.
- **Recargo actual** (`markup_pct`):
  `(shelf_price_untaxed / replenishment_cost − 1) × 100`. Si el costo es 0 → sin
  cálculo. Se usa recargo sobre costo (no margen sobre precio) porque es como se habla en
  el comercio argentino ("le pongo 40 arriba").
- **Recargo objetivo**: el `sale_margin` del producto (margen del precio planificado de
  Adhoc), que el punto 1 hereda de la categoría salvo "margen propio". Es la misma
  definición: precio sin impuestos = costo × (1 + margen).

## Modelo de datos

### `res.company`
- `shelf_pricelist_id` (M2O `product.pricelist`).
- `markup_tolerance_pct` (Float, default 2): tolerancia antes de alertar.

### `product.price.watch` (nuevo)

Una fila por (producto, empresa), restricción única. La escribe el proceso de refresco
(no son computes de ORM: el precio depende de la fecha y de datos no almacenados).

| Campo | Tipo | Notas |
|---|---|---|
| `product_tmpl_id` | M2O, `ondelete='cascade'` | requerido |
| `company_id` | M2O | requerido |
| `shelf_price` | Float | precio de góndola al último refresco |
| `shelf_price_untaxed` | Float | |
| `replacement_cost` | Float | `replenishment_cost` de Adhoc al último refresco |
| `markup_pct` | Float, computado almacenado | |
| `target_markup_pct` | related `product_tmpl_id.sale_margin` | |
| `markup_alert` | Selection `ok`/`below`/`no_cost`, computado almacenado | `below` si `markup_pct < target − tolerancia` |
| `label_printed_price` | Float | precio de la última etiqueta 3x8 regular impresa |
| `label_printed_date` | Datetime | |
| `label_variation_pct` | Float, computado almacenado | `shelf_price / label_printed_price − 1` |
| `label_pending` | Boolean, computado almacenado | `float_compare(shelf_price, label_printed_price, 2) != 0` |
| `refreshed_at` | Datetime | |

## Refresco

`product.price.watch._refresh(templates, company)`: calcula precio de góndola, sin
impuestos y reposición, y crea o actualiza las filas. Se ejecuta:

- **Cron diario** `_cron_refresh`: por empresa, sobre productos `sale_ok` activos de esa
  empresa o sin empresa, en lotes de 1000 con `commit` entre lotes (fuera de tests).
- **Botón "Actualizar"** en las listas (sobre las filas seleccionadas).

## Impresión

- Override de `product.label.layout.process()`: con `print_format == '3x8xprice'`,
  refresca las filas de los productos impresos y escribe `label_printed_price` = precio
  calculado con **la lista elegida en el wizard** (o `list_price` si no eligió) y
  `label_printed_date = now`. Si la lista del wizard difiere de la de góndola, el precio
  impreso no coincide con el controlado y el producto **sigue pendiente**.
- Las etiquetas de promoción (`3x8xpromo`) **no** tocan la cola.
- **Advertencia** en el wizard si la lista elegida difiere de la lista de góndola de la
  empresa (el precio impreso no coincidiría con el controlado).

## Instalación

`post_init_hook`: para cada empresa, corre el refresco y setea
`label_printed_price = shelf_price` para que al instalar **no** queden todos los
productos pendientes.

## Interfaz

- Menú **Inventario → Productos → Etiquetas pendientes**: lista de `product.price.watch`
  con `label_pending`, columnas precio impreso, precio actual, variación %, fecha de
  impresión; botones "Imprimir etiquetas" (abre `product.label.layout` con
  `print_format='3x8xprice'`, la lista de góndola y los productos seleccionados) y
  "Actualizar".
- Menú **Compras → Productos → Margen erosionado**: filas con
  `markup_alert = 'below'`, columnas reposición, precio sin impuestos, recargo actual,
  recargo objetivo.
- Wizard de etiquetas: aviso si la lista elegida difiere de la de góndola.
- Ajustes: lista de góndola y tolerancia.

## Actualizar precio planificado

El precio sugerido es el **precio planificado de Adhoc** (`product_planned_price`):
costo de reposición × (1 + margen) + recargo, con impuestos incluidos. Desde **Margen
erosionado**, el botón **"Actualizar precio planificado"** (gerentes de compras) lo pasa al
precio de venta de las filas seleccionadas que tienen precio "por margen", con el método de
Adhoc (`_update_prices_from_planned`), y refresca las filas: quedan en la cola de
etiquetas. Los productos con precio manual se informan en un aviso.

Adhoc escribe `list_price` por SQL: después hay que invalidar la caché antes de refrescar.
`list_price` no depende de la empresa. Se documenta en el README.

## Redondeo comercial (sin código)

El core ya lo cubre en las reglas de lista (`price_round`, `price_surcharge`,
`price_min_margin`, `price_max_margin`). Ejemplos a documentar en el README:
- Terminar en 99: redondeo 100, recargo −1.
- Múltiplos de 50: redondeo 50.

## Seguridad

- Ver colas y alertas: usuarios de inventario/ventas/compras.
- El margen (categoría y producto) lo gestiona el punto 1. Lista de góndola y tolerancia:
  quien acceda a Ajustes.
- `product.price.watch`: lectura para usuarios internos; escritura sólo por el
  proceso de refresco/impresión (`sudo`). Record rule multi-company.

## Tests

1. Refresco: `shelf_price` con impuestos incluidos, con y sin lista de góndola.
2. Recargo actual y alerta `below`/`ok`/`no_cost` con tolerancia.
4. Cola: con precio "por margen", sube el costo y se actualiza el precio planificado →
   pendiente después del refresco;
   imprimir 3x8 regular → no pendiente; imprimir promo → sigue pendiente.
5. `post_init_hook`: nada pendiente al instalar.
6. Multi-company: filas independientes por empresa.
7. Actualizar precio planificado: productos "por margen" cambian de precio y quedan en la
   cola; productos con precio manual se informan.

## Decisiones a validar (tomadas sin consultar)

1. **Recargo sobre costo**, no margen sobre precio de venta.
2. Detección por **snapshot + refresco** (cron diario + botón), no en tiempo real: el
   precio depende de datos no almacenados y fechas de vigencia. Sin refresco automático
   al aplicar importaciones o programaciones (YAGNI: el botón y el cron alcanzan).
3. La cola se vacía al **imprimir**, no al confirmar que la etiqueta se colocó.
4. Solo etiquetas **3x8 regulares** alimentan la cola; otros formatos de Odoo no.
5. Snapshots en un **modelo propio** por (producto, empresa).
6. "Actualizar precio planificado" escribe `list_price` directo (sin vista previa): el
   usuario elige las filas en la lista antes de aplicar.
