# AlparData - Margen Erosionado y Etiquetas Pendientes (`alpardata_price_change_labels`)

Módulo para Odoo 19.0 desarrollado por AlparData.  
Punto 3 del roadmap de costo comercial para retail en Argentina (extiende `alpardata_purchase_replacement_cost` y `product_label_3x8`).

---

## 1. Problema que resuelve

En un contexto inflacionario con frecuentes aumentos de costos de reposición de proveedores, el retail enfrenta un dilema crítico:

1. **Margen erosionado (precios fijos):** Si los precios de venta son fijos o no se recalculan de inmediato, los aumentos de costo de los proveedores reducen el margen comercial ("lo erosionan") silenciosamente, vendiendo por debajo de la rentabilidad esperada sin que compras o gerencia se enteren a tiempo.
2. **Etiquetas de góndola desactualizadas (precios por fórmula):** Si los precios se calculan automáticamente sobre el costo de reposición (`replacement_cost`) mediante reglas dinámicas de tarifa, el sistema actualiza el precio de venta al instante. Sin embargo, **la etiqueta física exhibida en la góndola queda desactualizada**. En Argentina, la exhibición correcta, veraz y visible del precio en góndola es una obligación legal estricta (Res. 4/2025, Ley 27.743 y Ley de Defensa del Consumidor).

Este módulo resuelve ambos problemas en tiempo real:
* **Monitorea el recargo comercial:** Alerta cuando el margen sobre reposición queda por debajo del objetivo presupuestado.
* **Cola de etiquetas pendientes:** Identifica automáticamente todos los productos cuyo precio de góndola actual difiere del último impreso físicamente, sin importar qué originó la variación.

---

## 2. Conceptos Clave y Métricas

* **Lista de góndola (`shelf_pricelist_id`):** Tarifa definida en la empresa (**Ajustes → Compras → Costo de Referencia Comercial**) con la que se calcula el precio de venta al público en góndola. Si no se define ninguna, se utiliza el precio de venta base del producto (`list_price`).
* **Precio de góndola (`shelf_price`):** Precio final con impuestos calculado con **la misma función que genera las etiquetas 3x8** (`_get_label_info`). Lo que el sistema audita es exactamente lo que el cliente lee en la góndola.
* **Precio de góndola sin impuestos (`shelf_price_untaxed`):** Base neta sin IVA ni impuestos indirectos calculada dinámicamente según la estructura fiscal del artículo.
* **Recargo actual (`markup_pct`):**  
  $$\text{Recargo} = \left(\frac{\text{Precio sin impuestos}}{\text{Costo de reposición}} - 1\right) \times 100$$  
  *Se expresa como recargo sobre costo (% sobre costo o markup) siguiendo la convención habitual del comercio argentino (ej. "marcar al 40%").*
* **Recargo objetivo (`target_markup_pct`):** Margen comercial pretendido. Se define por **Categoría de Producto** y se hereda automáticamente al producto (donde puede ajustarse puntualmente si fuera necesario).
* **Tolerancia de alerta (`markup_tolerance_pct`):** Margen de gracia configurable por empresa (por defecto 2 puntos porcentuales). Si el recargo objetivo es 40% y la tolerancia es 2%, se emitirá una alerta si el recargo cae por debajo de 38%.

---

## 3. Alertas de Margen Erosionado

En el menú **Compras → Costos de Referencia → Margen erosionado**, compras y comercialización disponen de una vista dedicada con los productos en riesgo:

| Estado de Margen | Condición | Interpretación |
| :--- | :--- | :--- |
| **`OK`** (Verde) | $\text{Recargo actual} \ge \text{Objetivo} - \text{Tolerancia}$ | Rentabilidad preservada. |
| **`Bajo objetivo`** (Rojo) | $\text{Recargo actual} < \text{Objetivo} - \text{Tolerancia}$ | **Alerta:** el aumento de costo del proveedor comprimió el margen de venta. |
| **`Sin costo`** (Gris) | Costo de reposición es \$0,00 | Producto sin ficha de proveedor o sin costo asignado. |

---

## 4. Cola de Etiquetas Pendientes (`product.price.watch`)

En el menú **Inventario → Productos → Etiquetas pendientes**, el personal de tienda y almacén visualiza los productos cuyo precio físico de góndola debe reimprimirse:

1. **Ingreso automático en la cola:** Cada vez que cambia el precio (por aumento de reposición en tarifas por fórmula, por cotización o por cambio manual de precio de lista), el sistema detecta que $\text{Precio de Góndola} \neq \text{Precio Impreso}$.
2. **Información disponible:**
   * Precio anterior impreso y fecha de la última impresión.
   * Nuevo precio de venta de góndola.
   * Porcentaje de variación (coloreado en rojo para aumentos, verde para bajas).
3. **Impresión masiva:**
   * Se seleccionan los productos pendientes en la lista y se presiona **Imprimir etiquetas**.
   * El asistente abre el wizard con el formato `3x8xprice` y la lista de góndola preconfigurada.
   * Al confirmar la impresión, el sistema actualiza automáticamente el `label_printed_price` y la fecha, **removiendo los productos de la cola de pendientes**.
4. **Validaciones de impresión:**
   * **Etiquetas de promoción:** Imprimir formatos promocionales (`3x8xpromo`) no vacía la cola de pendientes, ya que el precio de oferta es transitorio y la etiqueta base de góndola sigue requiriendo actualización.
   * **Advertencia de lista:** Si en el wizard de impresión el usuario cambia la lista a una que no sea la de góndola, el sistema muestra un cartel de advertencia informando que los productos continuarán marcados como pendientes.

---

## 5. Procesos de Refresco (Cron y Manual)

El cálculo y comparación de precios se realiza mediante `product.price.watch._refresh`:
* **Cron diario automático:** Se ejecuta durante la noche actualizando la foto de precios de todos los productos vendibles activos en lotes de 1.000 artículos.
* **Botón "Actualizar":** Permite al usuario refrescar en el momento los productos seleccionados para verificar el impacto inmediato de un cambio de costos o precios.
* **Instalación (`post_init_hook`):** Al instalar el módulo por primera vez, se toma la foto inicial de precios y se asume como impresa para evitar que todo el catálogo ingrese artificialmente en la cola de pendientes.

---

## 6. Recomendaciones: Redondeo Comercial en Tarifas

Odoo estándar cubre el redondeo psicológico y comercial mediante las reglas de tarifas por fórmula. No se requiere desarrollo adicional para implementar las reglas de redondeo habituales en Argentina:

* **Precios terminados en 99 (ej. \$1.499 en lugar de \$1.423):**
  * **Método de redondeo:** `100.0`
  * **Recargo / Descuento adicional:** `-1.0`
  * *Efecto: redondea a la centena superior y resta \$1,00.*
* **Precios en múltiplos de \$50 (ej. \$1.450 en lugar de \$1.423):**
  * **Método de redondeo:** `50.0`
  * **Recargo / Descuento adicional:** `0.0`
* **Precios en múltiplos de \$10 (evitar monedas o cambio chico):**
  * **Método de redondeo:** `10.0`

---

## 7. Permisos de Seguridad

* **Visualización de cola y márgenes:** Disponible para todos los usuarios internos de compras, inventario y ventas (`base.group_user`).
* **Edición de recargo objetivo (`target_markup_pct`):** Protegido mediante `commercial.conditions.access.mixin`, reservado para **Gerentes de Compras (`purchase.group_purchase_manager`)**.
* **Configuración de lista de góndola y tolerancia:** Acceso restringido a los administradores con permiso en Ajustes de Compras.
