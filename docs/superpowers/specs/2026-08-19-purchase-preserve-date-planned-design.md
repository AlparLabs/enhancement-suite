# Preservar fecha prevista (date_planned) en órdenes de compra

**Fecha:** 2026-08-19
**Módulo:** purchase_preserve_date_planned
**Ramas objetivo:** 18.0 primero, port a 19.0

## Problema

En Odoo estándar (purchase.order.line), el campo date_planned se recalcula de forma automática dentro del método _compute_price_unit_and_date_planned_and_name.

Este método depende de:
`python
@api.depends('product_qty', 'product_uom', 'company_id', 'order_id.partner_id')
def _compute_price_unit_and_date_planned_and_name(self):
    ...
    if seller or not line.date_planned:
        line.date_planned = line._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
`

Cuando un producto tiene un proveedor asignado (seller no es nulo), la condición seller or not line.date_planned siempre resulta verdadera. En consecuencia:
1. Al modificar cantidades (product_qty), unidad de medida (product_uom) o proveedor, se sobreescribe cualquier fecha estimada fijada manualmente por el usuario.
2. La fecha de cabecera (purchase.order.date_planned) computa el mínimo de las fechas de las líneas, por lo que arrastra esta pérdida del valor manual.
3. El picking de recepción generado por purchase_stock toma la fecha de la línea, provocando fechas de entrega imprecisas o revertidas al plazo teórico del proveedor.

## Solución

Extender el modelo purchase.order.line sobreescribiendo el método _compute_price_unit_and_date_planned_and_name para capturar y preservar las fechas previstas que ya cuenten con un valor previo.

- Si line.date_planned ya tiene un valor (sea manual o heredado de la orden), se conserva durante el cálculo.
- Si line.date_planned está vacío (nueva línea agregada al pedido), se ejecuta el cálculo estándar por defecto (tiempo de entrega del proveedor / fecha del pedido).

## Alcance

### Incluido
- Módulo purchase_preserve_date_planned.
- Extensión limpia de purchase.order.line vía _compute_price_unit_and_date_planned_and_name.
- Suite de tests unitarios (TransactionCase) que validan:
  1. Nueva línea calcula date_planned por defecto según el proveedor.
  2. Modificación de product_qty preserva date_planned manual.
  3. Modificación de product_uom preserva date_planned.
  4. Cambio de date_planned en la cabecera actualiza líneas y la posterior edición de cantidades respeta el valor actualizado.

### Excluido, con motivo
- Interruptores de configuración por compañía: no requeridos, comportamiento deseado como estándar por defecto en compras.
- Modificación de vistas XML: no requerida, aprovecha los campos y flujo nativo de Odoo.

## Plan de entrega
1. Implementar y testear en la rama 18.0.
2. Portar a la rama 19.0 (mismo mecanismo de ORM).
