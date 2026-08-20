# Purchase - Preserve Date Planned

Modulo para Odoo 18.0 / 19.0 desarrollado por AlparData.

## Problema

En Odoo estandar, la fecha prevista (`date_planned`) en las lineas de compra (`purchase.order.line`) se recalcula automaticamente cada vez que se modifica la cantidad (`product_qty`), unidad de medida (`product_uom`) o proveedor, si el producto tiene plazos de entrega configurados (`seller_ids`).

Esto causaba que cualquier fecha estimada ingresada manualmente por el usuario o heredada de la cabecera se perdiera y se pisara con `date_order + plazo del proveedor`.

## Solucion

Este modulo extiende `purchase.order.line` para preservar el valor de `date_planned` si ya existe en la linea cuando se recomputan los precios y descripciones.
- En nuevas lineas sin fecha, se calcula inicialmente el plazo del proveedor por defecto.
- Una vez asignada una fecha, modificaciones posteriores en cantidades o unidades de medida respetan la fecha existente.
