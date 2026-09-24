# AlparData - Margen de Reposición en Punto de Venta (`alpardata_pos_replacement_margin`)

Módulo para Odoo 19.0 desarrollado por AlparData.  
Punto 5 del roadmap de costo comercial para retail en Argentina (extiende `point_of_sale` y `alpardata_purchase_replacement_cost`).

---

## 1. Problema que resuelve

En el comercio minorista y sucursales de retail, los tickets de Punto de Venta (POS) registran la salida diaria de mercadería. Odoo estándar calcula el margen de las ventas de mostrador contra el costo contable promedio (**AVCO**).

En épocas de alta inflación, vender en el mostrador por encima del AVCO no garantiza poder reponer la mercadería exhibida:
* Si vendés un producto a \$2.000 con un costo contable histórico de \$1.200, el sistema reporta un margen del 40%.
* Pero si la nueva lista del proveedor fija la reposición en \$2.100, cada ticket emitido genera una pérdida económica real.

Este módulo complementa el análisis de Punto de Venta incorporando el **Margen de Reposición (`replacement_margin`)**, permitiendo auditar la rentabilidad neta real de cada caja, sucursal o cajero.

---

## 2. Funcionamiento y Sincronización

### Momento de Captura del Costo
Al sincronizarse las órdenes desde la interfaz web del Punto de Venta (`pos.order.sync_from_ui`):
* Cada línea captura el costo de reposición unitario (`replacement_cost_unit`) vigente **a la fecha y hora de la orden (`date_order`)** utilizando `product.product._get_replacement_cost_for()`.
* Las devoluciones y notas de crédito de mostrador (cantidades negativas) computan el margen proporcionalmente en negativo.
* En productos tipo combo o sin costo configurado, se aplica el fallback a costo estándar.

### Tratamiento de Órdenes Históricas (`pre_init_hook`)
Al instalar el módulo, las columnas en `pos_order` y `pos_order_line` se crean inicializadas en 0 mediante un `pre_init_hook` de base de datos. Las ventas de mostrador anteriores a la instalación quedan sin margen de reposición a propósito para evitar falsear las estadísticas históricas con costos actuales.

---

## 3. Campos y Visualización

### En la Orden de POS (`pos.order`)
En la vista formulario del backend de pedidos de Punto de Venta:
* **Líneas de la orden (`pos.order.line`):** Columnas opcionales para **Costo de reposición** y **Margen de reposición**.
* **Pie de totales:** Campo **Margen de reposición** ubicado junto al margen estándar de la orden.

### En los Informes de Análisis de Punto de Venta (`report.pos.order`)
El análisis gráfico y tabla dinámica de Punto de Venta incorpora la medida **Margen de reposición**, con conversión de moneda por tipo de cambio de la sesión/orden, permitiendo comparar en paralelo el margen contable frente al margen real de reposición por punto de venta, categoría de POS o cajero.
