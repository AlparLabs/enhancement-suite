# AlparData - Margen de Reposición en Ventas (`alpardata_sale_replacement_margin`)

Módulo para Odoo 19.0 desarrollado por AlparData.  
Punto 5 del roadmap de costo comercial para retail en Argentina (extiende `sale_margin` y `alpardata_purchase_replacement_cost`).

---

## 1. Problema que resuelve

Odoo estándar (`sale_margin`) calcula el margen y la rentabilidad comercial comparando el precio de venta contra el costo contable promedio (**AVCO / `standard_price`**).

En contextos inflacionarios o de reposición continua (como el comercio en Argentina), esta métrica contable genera una **ilusión de ganancia**:
* Si compraste mercadería hace dos meses a \$1.000 (tu AVCO) y hoy reponerla cuesta \$1.600, vender a \$1.400 te reporta en el balance un margen contable positivo del 28,6% (\$400 de ganancia aparente).
* En la realidad comercial y de caja, **te estás descapitalizando**: con los \$1.400 cobrados no podés comprar nuevamente la unidad vendida (\$1.600), teniendo una pérdida real de reposición de -\$200.

Este módulo incorpora en el flujo de ventas el **Margen de Reposición (`replacement_margin`)** real, permitiendo a la empresa convivir con ambas métricas:
1. **Margen Contable (`margin`):** Lo que exige la contabilidad formal y el balance impositivo.
2. **Margen de Reposición (`replacement_margin`):** Lo que efectivamente queda en la empresa para sostener el capital de trabajo y reponer el stock.

---

## 2. Funcionamiento y Ciclo de Vida

### Momento de Captura del Costo
* **Al cotizar / cargar la línea:** Se obtiene el costo unitario de reposición vigente a la fecha del pedido (`replacement_cost_unit`) en la moneda y unidad de medida de la línea, utilizando el helper `_get_replacement_cost_for()`.
* **Al confirmar el pedido (`action_confirm`):** Debido a que un presupuesto de venta puede permanecer abierto durante semanas, al confirmar la venta se **recalcula automáticamente** el costo de reposición con las condiciones del día de la venta.

### Fallback a Costo Promedio (AVCO)
Si un producto vendido aún no posee ficha de proveedor con costo de reposición configurado, el sistema recurre de forma segura al costo estándar (`standard_price` / AVCO) e identifica la línea con el indicador técnico `replacement_cost_fallback = True`.

### Tratamiento de Pedidos Históricos (`pre_init_hook`)
Al instalar el módulo en una base de datos existente con pedidos históricos, las columnas se inicializan en 0 mediante un `pre_init_hook`. **No se recalculan pedidos viejos a propósito**: recalcular ventas pasadas con el costo de reposición de hoy generaría información falsa y distorsionada sobre la rentabilidad real de aquellos periodos.

---

## 3. Campos y Visualización

### En las Líneas del Pedido (`sale.order.line`)
Campos disponibles en la pestaña de líneas (columnas opcionales):
* **Costo de reposición (`replacement_cost_unit`):** Costo unitario neto-neto a la fecha de la venta.
* **Margen de reposición (`replacement_margin`):** Subtotal neto menos costo de reposición total.
* **Margen de reposición % (`replacement_margin_percent`):** Porcentaje de margen real sobre el precio de venta.

### En el Pie del Pedido (`sale.order`)
Junto al bloque estándar de margen contable de `sale_margin`:
* **Margen de reposición:** Total monetario en la moneda del pedido y porcentaje sobre el total sin impuestos.

### En los Informes de Análisis de Ventas (`sale.report`)
El reporte SQL de análisis de ventas suma la medida **Margen de reposición**, convirtiendo monedas según la tasa de cambio de la orden, para analizar la rentabilidad real en tablas dinámicas por cliente, producto, comercial o período.
