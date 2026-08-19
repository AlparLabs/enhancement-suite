# Diseño: stock_warehouse_user_access

**Fecha:** 2026-08-19
**Versión objetivo:** Odoo 18.0
**Patrón de referencia:** `stock_restrict_delivery` (mismo repo, reglas + grupo de excepción)

## Problema

Entorno multiempresa con varios almacenes y varios POS dentro de cada empresa.
La separación nativa de Odoo es por compañía, no por almacén, así que hoy un
usuario de una sucursal ve las transferencias y las órdenes de compra de todas
las sucursales de su empresa. Se necesita:

1. Que cada usuario vea únicamente los documentos de su almacén.
2. Que igual pueda hacer transferencias hacia otros almacenes, y que la punta
   receptora también vea esa transferencia.
3. Que en Compras el destino ("Entregar a") venga apuntado a su almacén, para
   evitar el error de mandar la mercadería a otra sucursal.

## Decisiones tomadas (con el usuario)

| Decisión | Elección |
|---|---|
| Asignación usuario→almacén | Campo many2many en `res.users` + almacén por defecto |
| Alcance | Transferencias (`stock.picking`) y Compras (`purchase.order`) |
| Transferencias entre almacenes | Visible si el tipo de operación **o** la ubicación origen **o** la destino pertenecen a un almacén del usuario |
| Excepción | Grupo dedicado nuevo "Ver todos los almacenes" (no se reutiliza `group_stock_manager`) |
| Compras | Ver solo las propias **y** forzar el destino |
| OC sin almacén (servicios/dropship) | Visibles para todos |
| Empaquetado | Un solo módulo, con `depends` en `purchase_stock` |
| Versión | Solo 18.0 |

## Hechos verificados contra el código de Odoo 18.0

Verificado en `C:\Program Files\Odoo 18.0.20260307\server\odoo\addons`:

- `stock.location.warehouse_id` es `compute='_compute_warehouse_id', store=True`
  (`stock/models/stock_location.py:92`). Al estar almacenado, **se puede usar en
  el dominio de una `ir.rule`**. Esta es la premisa de la que depende todo el
  diseño de visibilidad por ubicación.
- `purchase.order.picking_type_id` ("Deliver To") se define en
  **`purchase_stock`**, no en `purchase` (`purchase_stock/models/purchase_order.py:23`).
  Es `required=True` y su dominio nativo admite `warehouse_id = False`, que es
  el caso de los tipos dropship.
- Las reglas nativas `stock.stock_picking_rule` y `purchase.purchase_order_comp_rule`
  son **globales** (sin `groups_id`): se combinan con AND contra las nuestras.
  No existe ninguna regla permisiva por grupo sobre estos modelos que pueda
  anular la restricción por OR.
- `Environment.user` devuelve el registro **sudoed** (`odoo/api.py:687-692`), así
  que leer `user.warehouse_access_ids` dentro del evaluador de `ir.rule` no
  choca contra `SELF_READABLE_FIELDS` de `res.users`.

## Modelo de datos

### `res.users`

- `warehouse_access_ids` (Many2many → `stock.warehouse`, "Almacenes permitidos").
  Tabla de relación propia. Sin valor por defecto.
- `default_warehouse_id` (Many2one → `stock.warehouse`, "Almacén por defecto").
  Su dominio en la vista se limita a `warehouse_access_ids`.

Constraint Python: si `default_warehouse_id` está cargado, debe pertenecer a
`warehouse_access_ids`. Mensaje de error explícito.

Ambos campos se muestran en el formulario de usuario, en la pestaña de permisos
de acceso, junto al grupo de excepción.

### Grupo

- `group_warehouse_access_all` — "Ver todos los almacenes", categoría
  `base.module_category_inventory_inventory`. No implica ningún otro grupo: se
  puede otorgar a un administrativo sin convertirlo en gerente de stock.

## Seguridad

Patrón estándar de Odoo para "restringir con excepción": las reglas asociadas a
grupos se combinan entre sí con **OR**, y el conjunto se combina con AND contra
las reglas globales. Por lo tanto cada modelo lleva un par de reglas.

La regla restrictiva se ancla en **`base.group_user`**, no en
`stock.group_stock_user`. Motivo: si se anclara en el grupo de inventario, un
usuario que no lo tenga (por ejemplo un cajero de POS) quedaría sin ninguna
regla de grupo aplicable sobre el modelo, y en ese caso Odoo solo aplica las
globales — es decir, vería todo.

### `stock.picking`

Restrictiva (`base.group_user`):

```python
['|', '|', '|',
 ('picking_type_id.warehouse_id', '=', False),
 ('picking_type_id.warehouse_id', 'in', user.warehouse_access_ids.ids),
 ('location_id.warehouse_id', 'in', user.warehouse_access_ids.ids),
 ('location_dest_id.warehouse_id', 'in', user.warehouse_access_ids.ids)]
```

Permisiva (`group_warehouse_access_all`): `[(1, '=', 1)]`.

La rama de ubicaciones es la que resuelve el caso de la transferencia entre
almacenes: un albarán interno pertenece al tipo de operación de un solo almacén
(el origen), así que sin esa rama el almacén destino no vería la mercadería que
le está llegando.

### `purchase.order`

Restrictiva (`base.group_user`):

```python
['|', '|',
 ('picking_type_id', '=', False),
 ('picking_type_id.warehouse_id', '=', False),
 ('picking_type_id.warehouse_id', 'in', user.warehouse_access_ids.ids)]
```

Permisiva (`group_warehouse_access_all`): `[(1, '=', 1)]`.

Las dos primeras ramas implementan la decisión "las OC sin almacén las ve todo
el mundo": cubren servicios y dropship, cuyos tipos de operación tienen
`warehouse_id = False`.

### Falla cerrado

Un usuario sin almacenes cargados y sin el grupo de excepción **no ve nada**,
salvo los documentos sin almacén. Es el comportamiento correcto en seguridad,
pero implica que instalar el módulo sin preparar los usuarios deja pantallas
vacías.

Mitigación: `post_init_hook` que, al instalar, otorga
`group_warehouse_access_all` a todos los usuarios internos que ya pertenezcan a
`stock.group_stock_manager` o a `purchase.group_purchase_manager`. Nadie con
rol de gerencia queda encerrado el día 1; el resto se configura almacén por
almacén. El hook no toca usuarios portal ni públicos, y es idempotente.

## Restricción de los desplegables

**No** se aplica una `ir.rule` sobre `stock.picking.type`. Una regla de lectura
sobre ese modelo rompe maquinaria interna: las rutas de reabastecimiento y las
confirmaciones que generan albaranes de otro almacén fallarían con `AccessError`
cuando corren bajo el usuario. En su lugar, filtrado por contexto:

### `stock.picking.type._search`

Override que antepone el filtro por almacén al dominio **solo si** se cumplen
las dos condiciones:

1. El contexto trae `restrict_to_user_warehouses` en verdadero.
2. El usuario no pertenece a `group_warehouse_access_all`.

Dominio inyectado:

```python
['|',
 ('warehouse_id', '=', False),
 ('warehouse_id', 'in', self.env.user.warehouse_access_ids.ids)]
```

Si el usuario no tiene almacenes cargados, el override no filtra nada: la
restricción real ya la aplican las reglas de registro, y filtrar acá solo
produciría un desplegable vacío sin explicación.

### Puntos donde se activa el contexto

- Campo `picking_type_id` del formulario de orden de compra ("Entregar a").
- Campo `picking_type_id` del formulario de transferencia.
- Acción del panel de Inventario (`stock.stock_picking_type_action`, la del menú
  "Resumen" en vista kanban — no confundir con `stock.action_picking_type_list`,
  que es la lista de configuración de Tipos de Operación), para que el kanban
  muestre solo las tarjetas de operación de sus almacenes.

### Valores por defecto

- `purchase.order`: se extiende `_default_picking_type` de `purchase_stock` para
  preferir el tipo de recepción de `default_warehouse_id` del usuario, con
  fallback al comportamiento nativo si el usuario no tiene almacén por defecto o
  si ese almacén no pertenece a la compañía activa.
- `stock.picking`: mismo criterio sobre `_default_picking_type_id`.

### Alcance de esta capa

Es UX, no blindaje. Un usuario decidido podría apuntar a otro almacén por
importación o API. La consecuencia es que el documento resultante le
desaparecería de la vista por la regla de registro. Para el objetivo declarado
—evitar que se confundan de destino— es suficiente.

## Fuera de alcance

Decidido explícitamente, no es omisión:

- `purchase.order.line` y `purchase.report`: quedan cubiertos por la regla
  multiempresa nativa. Cerrarlos por almacén es sumar reglas al mismo módulo si
  más adelante hace falta.
- `stock.quant`, ajustes de inventario y reportes de existencias.
- Ventas (`sale.order`) y POS.

## Estructura del módulo

```
stock_warehouse_user_access/
├── __init__.py
├── __manifest__.py                  # depends: stock, purchase_stock
├── hooks.py                         # post_init_hook
├── models/
│   ├── __init__.py
│   ├── res_users.py                 # campos + constraint
│   ├── stock_picking_type.py        # _search por contexto
│   ├── stock_picking.py             # default picking type
│   └── purchase_order.py            # _default_picking_type
├── security/
│   ├── warehouse_access_groups.xml  # group_warehouse_access_all
│   └── warehouse_access_rules.xml   # 4 ir.rule
├── views/
│   ├── res_users_views.xml
│   ├── purchase_order_views.xml     # contexto en picking_type_id
│   └── stock_picking_views.xml      # contexto + acción del panel
└── tests/
    ├── __init__.py
    └── test_warehouse_access.py
```

Strings de cara al usuario en español, en línea con el resto de la suite; no se
generan archivos `.po`.

## Tests

`TransactionCase` con dos almacenes (WH-A, WH-B) en la misma compañía y tres
usuarios: `user_a` (solo WH-A), `user_b` (solo WH-B), `user_all` (grupo de
excepción, sin almacenes).

1. `user_a` ve un albarán cuyo tipo de operación es de WH-A.
2. `user_a` **no** ve un albarán cuyo tipo de operación es de WH-B.
3. Transferencia interna WH-A → WH-B: la ven **tanto** `user_a` como `user_b`.
4. `user_all` ve los tres albaranes anteriores.
5. Usuario sin almacenes y sin el grupo de excepción no ve ninguno.
6. `user_a` no ve una OC cuyo "Entregar a" apunta a WH-B.
7. Una OC con tipo de operación dropship (`warehouse_id = False`) la ven
   `user_a`, `user_b` y `user_all`.
8. El default de `picking_type_id` en una OC creada por `user_a` resuelve al
   tipo de recepción de WH-A.
9. `_search` de `stock.picking.type` con `restrict_to_user_warehouses` devuelve
   solo los tipos de WH-A para `user_a`, y todos para `user_all`.
10. La constraint rechaza un `default_warehouse_id` fuera de
    `warehouse_access_ids`.
