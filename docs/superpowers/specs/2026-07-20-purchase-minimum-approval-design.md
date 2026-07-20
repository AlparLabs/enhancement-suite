# Diseño: purchase_minimum_approval

**Fecha:** 2026-07-20
**Versión objetivo:** Odoo 18.0
**Patrón de referencia:** `sale_credit_limit_approval` (mismo repo)

## Problema

Algunos proveedores exigen un monto mínimo de compra. Hoy nada impide confirmar
una orden de compra por debajo de ese mínimo. Se necesita:

1. Configurar por proveedor si aplica mínimo y cuál es el monto.
2. Bloquear la confirmación de órdenes por debajo del mínimo.
3. Permitir que un grupo aprobador autorice excepciones.

Es el análogo para compras del flujo de límite de crédito en ventas.

## Decisiones tomadas (con el usuario)

| Decisión | Elección |
|---|---|
| Comportamiento al no llegar al mínimo | Bloqueo + flujo de aprobación (estado `waiting_approval`) |
| Monto a comparar | Subtotal sin impuestos (`amount_untaxed`) |
| Mecanismo de aprobación | Solo grupo aprobador (sin PIN, sin dependencia de `hr`) |
| Moneda del mínimo | Moneda de la compañía; el subtotal de la orden se convierte al comparar |
| Supervisor por proveedor | No; la aprobación es exclusivamente por grupo |

## Modelo de datos

### `res.partner`

- `apply_purchase_minimum` (Boolean, "Aplica mínimo de compra", tracking).
- `purchase_minimum_amount` (Monetary, "Mínimo de compra", moneda de la
  compañía vía `currency_id` nativo del partner, tracking).

Ambos campos se leen siempre desde `commercial_partner_id`: un mínimo definido
en la empresa aplica a todos sus contactos hijos.

### `purchase.order`

- `state`: `selection_add=[('waiting_approval', 'Esperando Aprobación')]`,
  `ondelete={'waiting_approval': 'set default'}`.
- `minimum_approval_note` (Char, readonly, copy=False): motivo del bloqueo,
  visible en la vista.
- `purchase_minimum_warning` (Char, computed, no almacenado): mensaje de alerta
  que se muestra como banner en el formulario ya en borrador, cuando el
  subtotal no llega al mínimo.
- `show_approve_minimum_button` (Boolean, computed): visibilidad del botón de
  aprobación (estado `waiting_approval` + usuario en el grupo aprobador).

## Flujo

### Chequeo (`_check_purchase_minimum`)

Devuelve `True` si la orden queda por debajo del mínimo:

1. Partner efectivo: `partner_id.commercial_partner_id`.
2. Si `apply_purchase_minimum` es falso o `purchase_minimum_amount <= 0` → no
   bloquea.
3. Convierte `amount_untaxed` de la moneda de la orden a la moneda de la
   compañía (`currency_id._convert(...)` a `date_order`).
4. Compara con `float_compare` usando el redondeo de la moneda de compañía.

### Confirmación (`button_confirm`)

- Contexto `bypass_purchase_minimum=True` → saltea el chequeo (usado tras
  aprobar).
- Para órdenes en `draft`/`sent` que no llegan al mínimo: se escriben
  `state='waiting_approval'` y `minimum_approval_note`, y se registra mensaje
  en el chatter con mínimo vs. subtotal. No se confirman.
- Las que superan el mínimo (o no aplican) se confirman normalmente con
  `super()`.

### Aprobación (`action_approve_minimum`)

- Solo estado `waiting_approval` (sino `UserError`).
- Solo miembros del grupo aprobador (sino `AccessError`).
- Registra la aprobación en el chatter, resetea `state='draft'` y limpia la
  nota, luego llama `button_confirm` con `bypass_purchase_minimum=True`.

### Cancelación (`button_cancel`)

Las órdenes en `waiting_approval` pasan a `cancel` directamente (limpiando la
nota); el resto sigue el flujo estándar.

## Seguridad

Grupo `group_purchase_minimum_approver` ("Compras: Aprobar Mínimo de Compra"),
categoría `base.module_category_inventory_purchase`, con
`implied_ids=[purchase.group_purchase_user]`.

No hay modelos nuevos → no se necesita `ir.model.access.csv`.

## Vistas

- **Partner:** en la pestaña Compras (`purchase.view_partner_property_form`),
  check + monto (monto visible solo con el check activo).
- **Orden de compra:**
  - Banner de alerta (`alert-warning`) con `purchase_minimum_warning` cuando
    hay texto.
  - Campo `minimum_approval_note` visible en `waiting_approval`.
  - Botón "Aprobar mínimo" (primario) visible según
    `show_approve_minimum_button`.
  - El estado nuevo aparece en el statusbar automáticamente por
    `selection_add`.

## Estructura del módulo

```
purchase_minimum_approval/
├── __init__.py
├── __manifest__.py            # depends: ['purchase'], version 18.0.1.0.0
├── models/
│   ├── __init__.py
│   ├── res_partner.py
│   └── purchase_order.py
├── security/
│   └── security.xml
├── views/
│   ├── res_partner_views.xml
│   └── purchase_order_views.xml
└── tests/
    ├── __init__.py
    └── test_purchase_minimum.py
```

Strings en español, consistentes con `sale_credit_limit_approval`.

## Tests (`TransactionCase`)

1. Proveedor sin mínimo → confirma directo.
2. Proveedor con mínimo y orden que lo supera → confirma directo.
3. Proveedor con mínimo y orden por debajo → queda en `waiting_approval` con
   nota y sin confirmar.
4. Aprobador ejecuta `action_approve_minimum` → orden confirmada (`purchase`).
5. Usuario no aprobador ejecuta `action_approve_minimum` → `AccessError`.
6. Mínimo definido en la empresa madre bloquea órdenes a un contacto hijo.
7. Orden en otra moneda: la conversión a moneda de compañía decide el bloqueo.
8. Cancelar una orden en `waiting_approval` → `cancel`.

## Fuera de alcance

- Aprobación por PIN de empleado.
- Supervisor/aprobador individual por proveedor.
- Mínimos por moneda del proveedor o por cantidad/unidades.
- Bloqueo en RFQ enviada (solo se chequea al confirmar; el banner avisa antes).
