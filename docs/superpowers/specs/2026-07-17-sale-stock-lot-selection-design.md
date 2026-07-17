# Diseño: `sale_stock_lot_selection` — Selección de lotes por el vendedor en la venta

**Fecha:** 2026-07-17
**Versión Odoo:** 19.0
**Estado:** Aprobado por Santiago Tojo
**Módulo relacionado:** `stock_forecasted_lots` (dependencia)

## Problema

Cuando un comercial vende un producto con seguimiento por lote (ej.: cable por
metro, cada lote es una bobina), la decisión de qué lote entregar queda en manos
del equipo de inventario, que muchas veces no tiene la comunicación con el
cliente que sí tuvo el vendedor. El vendedor necesita poder indicar, desde la
cotización, qué lote(s) específicos entregar — como ya permite el POS nativo de
Odoo — sin romper el mecanismo de reserva automática cuando no lo hace.

## Solución

En la línea de cotización de un producto con tracking por lote, un botón abre un
popup con los lotes disponibles del almacén de la orden. El vendedor indica
cuánto tomar de cada lote. Al confirmar la orden, esos lotes se reservan de
inmediato en la entrega. Todo lo que el vendedor no cubra —o que ya no esté
disponible al momento de confirmar— lo reserva Odoo con su estrategia normal
(FIFO/FEFO según configuración).

## Alcance y decisiones

- **La selección es opcional.** Sin selección, el comportamiento nativo queda
  100% intacto (el override no toca movimientos sin lotes pedidos).
- **Fallback automático.** Si el lote pedido se agotó o no alcanza, se reserva
  lo que haya de ese lote y el resto sigue la estrategia de remoción nativa.
  No hay bloqueos ni errores por indisponibilidad.
- **Solo productos con `tracking = 'lot'`** (los de número de serie quedan
  afuera, igual que en `stock_forecasted_lots`).
- **Editable solo en borrador/enviada.** Al confirmar la orden, la selección
  dispara la reserva y queda de solo lectura.
- **Reserva inmediata al confirmar.** Tras `action_confirm()`, se fuerza
  `action_assign()` solo en las entregas cuyas líneas tienen lotes pedidos,
  sin esperar al planificador ni a la política de reserva del tipo de operación.
- **Indicador visual en la línea** (pedido explícito del cliente): campo
  calculado con tres estados:
  - *no aplica* — producto sin tracking por lote: no se muestra nada;
  - *pendiente* — producto con lote y sin selección: botón en amarillo/warning
    con ícono de alerta ("Sin lote elegido");
  - *seleccionado* — botón en verde con la cantidad de lotes elegidos.
  Es informativo, no bloquea la confirmación.
- **Cantidades en la UdM del producto** (igual que los quants y que
  `stock_forecasted_lots`); si la línea vende en otra UdM, la validación de
  suma convierte la cantidad de la línea a la UdM del producto.
- **v1 no notifica** al vendedor si su lote no alcanzó al confirmar; la entrega
  muestra lo realmente reservado. Mejora futura posible: nota en el chatter de
  la orden con el detalle de lo reservado vs. lo pedido.

## Arquitectura

Módulo nuevo `sale_stock_lot_selection` en la raíz del repo (convenciones de la
suite: versión `19.0.1.0.0`, autor AlparData, LGPL-3).
`depends: ['sale_stock', 'stock_forecasted_lots']`.

```
sale_stock_lot_selection/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── sale_order.py          # action_confirm → forzar action_assign
│   ├── sale_order_line.py     # o2m lotes pedidos + estado visual + acción botón
│   ├── sale_order_line_lot.py # modelo nuevo: lote pedido por el vendedor
│   └── stock_move.py          # override _action_assign
├── wizard/
│   ├── __init__.py
│   └── lot_selection_wizard.py
├── views/
│   ├── sale_order_views.xml
│   └── lot_selection_wizard_views.xml
├── security/
│   └── ir.model.access.csv
├── i18n/
│   └── es_AR.po
└── tests/
    ├── __init__.py
    └── test_lot_selection.py
```

### Modelo de datos

`sale.order.line.lot` (nuevo, persistente):
- `sale_line_id` — Many2one a `sale.order.line`, required, ondelete cascade.
- `lot_id` — Many2one a `stock.lot`, required.
- `quantity` — Float, en la UdM del producto.

Restricciones:
- El lote debe pertenecer al producto de la línea.
- `quantity > 0`.
- La suma de cantidades pedidas de una línea no puede superar la cantidad de
  la línea (convertida a la UdM del producto). Puede ser menor: el resto cae
  a la reserva automática.
- Un mismo lote no puede repetirse en la misma línea (unicidad lote+línea).

`sale.order.line` (extensión):
- `requested_lot_ids` — One2many al modelo anterior.
- `lot_selection_status` — Selection calculado: `not_applicable` / `pending` /
  `selected`, según tracking del producto y existencia de lotes pedidos.
- Acción de botón que abre el wizard.

### Wizard de selección

`sale.line.lot.selection.wizard` (transient) con líneas
(`lot_id`, `available_quantity` solo lectura, `quantity_to_take`):
- Muestra en la cabecera dos totales de ayuda al vendedor (pedido explícito
  del cliente): **Cantidad a vender** (la cantidad de la línea, en la UdM del
  producto) y **Pendiente de asignar** (cantidad de la línea menos la suma de
  lo cargado en el wizard, recalculado en vivo mientras el vendedor tipea; lo
  pendiente se reserva con la estrategia automática).
- Se precarga con los lotes disponibles llamando a la lógica ya probada de
  `stock_forecasted_lots` (`stock.forecasted_product_product._get_lots_data`),
  con el almacén de la orden en el contexto — mismo criterio de ubicaciones
  (`view_location_id`, usage internal) y mismo orden ascendente por disponible
  (bobinas más vaciadas primero).
- Si la línea ya tenía lotes pedidos, precarga esas cantidades.
- Al confirmar, reemplaza los `requested_lot_ids` de la línea.

### Reserva (override de `stock.move._action_assign`)

Para los movimientos que cumplen TODAS estas condiciones:
- `sale_line_id` con `requested_lot_ids`,
- estado reservable (`confirmed` / `partially_available`),
- primer eslabón de la cadena (`move_orig_ids` vacío — sacan de stock físico,
  no de un movimiento previo),

antes de la reserva nativa se recorre cada lote pedido y se reserva
`min(cantidad pedida del lote, cantidad que falta reservar del movimiento,
disponible real del lote en la ubicación origen)` usando el mecanismo interno
de reserva de quants de Odoo. Después se llama a `super()._action_assign()`,
que completa el faltante con la estrategia de remoción nativa. Ese `super()`
es el fallback: no hay lógica propia de "siguiente lote".

Notas:
- Las firmas exactas de los métodos internos de reserva de Odoo 19
  (`_update_reserved_quantity` / `_get_available_quantity`) se verifican contra
  el código fuente en la fase de plan, igual que se hizo con
  `stock_forecasted_lots`.
- **Backorders:** el movimiento partido conserva `sale_line_id`, por lo que el
  remanente de un lote pedido se sigue prefiriendo en el backorder mientras
  tenga stock (siempre capado por disponibilidad real). Comportamiento aceptado
  para v1.
- **Entrega en 2 pasos (pick+ship):** los lotes se fuerzan solo en el pick;
  al ship llegan encadenados naturalmente vía `move_orig_ids`.

### Confirmación (override de `sale.order.action_confirm`)

Tras `super().action_confirm()`, para las entregas generadas cuyas líneas de
venta tienen lotes pedidos, se llama a `picking.action_assign()` para que la
reserva ocurra en el momento. Entregas sin lotes pedidos no se tocan.

## Seguridad

`ir.model.access.csv`: CRUD sobre `sale.order.line.lot` y el wizard para el
grupo de usuarios de Ventas (`sales_team.group_sale_salesman`). Sin reglas de
registro nuevas: la visibilidad sigue la de la orden de venta contenedora.
Sin `sudo()`: la reserva corre con los permisos que ya requiere confirmar una
venta con entrega.

## Manejo de errores

- Suma pedida > cantidad de línea → `ValidationError` al guardar.
- Lote de otro producto → `ValidationError`.
- Lote sin stock al confirmar → sin error: se reserva 0 de ese lote y el
  resto sigue el flujo nativo.
- Producto sin tracking por lote → botón invisible; si por datos llegara a
  haber lotes pedidos, el override los ignora (la condición de tracking se
  re-chequea en `_action_assign`).

## Pruebas

Tests Python (`tests/test_lot_selection.py`, tag `post_install`):

1. Lote pedido con stock suficiente → al confirmar, las move lines de la
   entrega reservan exactamente ese lote y esa cantidad.
2. Lote pedido insuficiente → reserva lo disponible de ese lote y completa
   con otro lote (fallback nativo).
3. Sin selección → reserva idéntica al comportamiento nativo (sin regresión).
4. Suma pedida > cantidad de línea → `ValidationError`.
5. Lote de otro producto → `ValidationError`.
6. Reparto entre dos lotes pedidos → ambos reservados con sus cantidades.
7. Producto sin tracking → `lot_selection_status = 'not_applicable'` y sin
   efecto en la reserva.
8. Estado visual: sin selección → `pending`; con selección → `selected`.

La parte visual (botón, colores, wizard) se verifica manualmente en la
instancia; sin runtime de Odoo en el entorno de desarrollo, los tests se
validan por sintaxis y trazado manual, y su ejecución real queda para la
instancia del cliente/CI.
