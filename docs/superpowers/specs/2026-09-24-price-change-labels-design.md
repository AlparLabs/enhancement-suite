# Margen erosionado y cola de etiquetas pendientes

**Fecha:** 2026-09-24
**Módulo nuevo:** `alpardata_price_change_labels`
**Depende de:** `alpardata_purchase_replacement_cost` (punto 1), `product_label_3x8`
**Rama objetivo:** `19.0`
**Roadmap:** punto 3 de 5 (ver `2026-09-24-commercial-cost-roadmap.md`)

## Problema

Con inflación, lo que importa es cuánto tarda un aumento de costo en llegar a la góndola:

1. Si el precio de venta es fijo (`list_price` o regla de precio fijo), un aumento de
   costo **erosiona el margen** sin que nadie se entere.
2. Si el precio se calcula desde el costo (regla de lista con base reposición), el
   precio cambia solo, pero **la etiqueta de la góndola queda vieja**. En Argentina el
   precio exhibido es obligatorio (Res. 4/2025, Ley 27.743, ya contemplados en
   `product_label_3x8`).

## Objetivo

- Detectar productos cuyo margen sobre reposición quedó por debajo del objetivo.
- Mantener una **cola de etiquetas pendientes**: productos cuyo precio de góndola actual
  difiere del último impreso, sin importar la causa (costo, cotización, regla de lista,
  cambio manual).

## Definiciones

- **Lista de góndola**: `res.company.shelf_pricelist_id` (configurable en Ajustes →
  Ventas). Si está vacía, se usa `list_price`.
- **Precio de góndola** (`shelf_price`): precio de la lista de góndola para cantidad 1,
  **con impuestos incluidos** (`taxes_id.compute_all(...)['total_included']`), en la
  moneda de la empresa.
- **Precio de góndola sin impuestos** (`shelf_price_untaxed`): `total_excluded`.
- **Recargo actual** (`current_markup_pct`):
  `(shelf_price_untaxed / replacement_cost − 1) × 100`. Si `replacement_cost = 0` → sin
  cálculo. Se usa recargo sobre costo (no margen sobre precio) porque es como se habla en
  el comercio argentino ("le pongo 40 arriba").
- **Recargo objetivo** (`target_markup_pct`): en la categoría; en el producto como
  computado almacenado editable, tomado de la categoría (mismo patrón que
  `internal_tax_pct` del punto 1).

## Modelo de datos

### `res.company`
- `shelf_pricelist_id` (M2O `product.pricelist`).
- `markup_tolerance_pct` (Float, default 2): tolerancia antes de alertar.

### `product.category`
- `target_markup_pct` (Float).

### `product.template`
Campos `company_dependent=True` (cada empresa tiene su lista y su góndola), actualizados
por el proceso de refresco (no son computes de ORM, porque el precio depende de la fecha
y de datos no almacenados):

| Campo | Tipo | Notas |
|---|---|---|
| `target_markup_pct` | Float, computado almacenado editable desde `categ_id` | no company-dependent |
| `shelf_price_snapshot` | Float | precio de góndola al último refresco |
| `markup_snapshot_pct` | Float | recargo actual al último refresco |
| `markup_alert` | Selection `ok`/`below`/`no_cost` | |
| `label_printed_price` | Float | precio de la última etiqueta 3x8 regular impresa |
| `label_printed_date` | Datetime | |
| `label_pending` | Boolean | `shelf_price_snapshot != label_printed_price` (comparación con `float_compare` a 2 decimales) |
| `price_watch_date` | Datetime | último refresco |

`markup_alert = 'below'` si `markup_snapshot_pct < target_markup_pct − markup_tolerance_pct`.

## Refresco

`product.template._refresh_price_watch()` sobre un recordset, bajo una empresa:
calcula `shelf_price`, `shelf_price_untaxed`, `current_markup_pct` y escribe los
snapshots. Se ejecuta:

- **Cron diario** `_cron_refresh_price_watch`: por cada empresa con
  `shelf_pricelist_id` o con productos vendibles, sobre productos `sale_ok` activos, en
  lotes de 1000 con `commit` entre lotes (patrón de crons largos de Odoo).
- **Botón "Actualizar ahora"** en las vistas de alerta y cola (sobre los seleccionados o
  todo si no hay selección).
- **Al aplicar** una importación del punto 2 o una programación de costo (si el módulo
  está instalado, vía override liviano de `action_apply`/`_apply_cost_change` que llama
  `_refresh_price_watch` sobre los productos tocados). Opcional: si complica, queda solo
  el cron.

## Impresión

- Override de `product.label.layout.process()`: después de generar el reporte con
  `print_format == '3x8xprice'`, escribe `label_printed_price = shelf_price` (recalculado
  en ese momento con la lista usada en el wizard, o la de góndola si no se eligió),
  `label_printed_date = now`, `label_pending = False` en los productos impresos.
- Las etiquetas de promoción (`3x8xpromo`) **no** tocan la cola.
- **Advertencia** en el wizard si la lista elegida difiere de la lista de góndola de la
  empresa (el precio impreso no coincidiría con el controlado).

## Instalación

`post_init_hook`: para cada empresa, corre el refresco y setea
`label_printed_price = shelf_price_snapshot` para que al instalar **no** queden todos los
productos pendientes.

## Interfaz

- Menú **Inventario → Productos → Etiquetas pendientes** (y en Ventas → Productos):
  lista de productos con `label_pending`, columnas precio anterior (impreso), precio
  nuevo, variación %, fecha de impresión; acción de servidor "Imprimir etiquetas" que
  abre `product.label.layout` con `print_format='3x8xprice'` y los productos
  seleccionados.
- Menú **Compras → Productos → Margen erosionado**: productos con `markup_alert = 'below'`,
  columnas reposición, precio sin impuestos, recargo actual, recargo objetivo.
- Filtros "Etiqueta pendiente" y "Margen bajo objetivo" en la búsqueda de productos.
- Ajustes: lista de góndola y tolerancia.

## Redondeo comercial (sin código)

El core ya lo cubre en las reglas de lista (`price_round`, `price_surcharge`,
`price_min_margin`, `price_max_margin`). Ejemplos a documentar en el README:
- Terminar en 99: redondeo 100, recargo −1.
- Múltiplos de 50: redondeo 50.

## Seguridad

- Ver colas y alertas: usuarios de inventario/ventas/compras.
- Editar `target_markup_pct` (categoría y producto), lista de góndola y tolerancia:
  managers de ventas o compras.
- No hay modelos nuevos → no hay ACL nuevas.

## Tests

1. Refresco: `shelf_price` con impuestos incluidos, con y sin lista de góndola.
2. Recargo actual y alerta `below`/`ok`/`no_cost` con tolerancia.
3. `target_markup_pct` desde categoría y pisado a mano.
4. Cola: cambio de costo con regla base reposición → pendiente después del refresco;
   imprimir 3x8 regular → no pendiente; imprimir promo → sigue pendiente.
5. `post_init_hook`: nada pendiente al instalar.
6. Multi-company: snapshots independientes por empresa.

## Decisiones a validar (tomadas sin consultar)

1. **Recargo sobre costo**, no margen sobre precio de venta.
2. Detección por **snapshot + refresco** (cron diario + botón), no en tiempo real: el
   precio depende de datos no almacenados y fechas de vigencia.
3. La cola se vacía al **imprimir**, no al confirmar que la etiqueta se colocó.
4. Solo etiquetas **3x8 regulares** alimentan la cola; otros formatos de Odoo no.
5. Snapshots **por empresa** (`company_dependent`).
