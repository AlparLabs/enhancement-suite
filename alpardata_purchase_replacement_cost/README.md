# AlparData - Costo de Reposición (`alpardata_purchase_replacement_cost`)

Módulo para Odoo 19.0 desarrollado por AlparData.  
Punto 1 del roadmap de costo comercial para retail en Argentina (extiende `alpardata_purchase_reference_cost`).

---

## 1. Problema que resuelve

En el comercio y retail de Argentina, el precio de catálogo o lista bruta del proveedor rara vez coincide con el costo real al que se repone la mercadería:

1. **Bonificaciones en cascada:** Los proveedores otorgan condiciones como `10+5+3` donde cada descuento se aplica sobre el neto resultante del anterior (no se suman aritméticamente). Odoo estándar solo dispone de un único campo de descuento.
2. **Costos adicionales y financieros:** Pronto pago, flete/logística, percepciones impositivas no recuperables (ej. IIBB) e impuestos internos (bebidas, tabaco) alteran el costo efectivo de reposición en góndola/almacén.
3. **Pérdida de competitividad o margen irreal:** Si las listas de precios de venta marcan margen sobre la lista bruta, el precio al público queda fuera de mercado; si se calcula sobre un costo incompleto, se pierde margen.

Este módulo introduce un **Costo de Reposición (`replacement_cost`)** desglosado y auditable por producto, disponible como base directa en las tarifas de venta, y aplica automáticamente las bonificaciones en cascada negociadas como descuento en las órdenes de compra.

---

## 2. Fórmula de cálculo y ejemplo canónico

Todos los adicionales se calculan sobre el **neto bonificado** (la base neta sobre la que factura el proveedor):

$$\text{Neto} = \text{Lista} \times (1 - b_1/100) \times (1 - b_2/100) \times \dots$$

$$\text{Costo de Reposición} = \text{Neto} \times \left(1 - \frac{\text{Pronto Pago}}{100} + \frac{\text{Flete}}{100} + \frac{\text{Percepción}}{100} + \frac{\text{Internos}}{100}\right)$$

### Ejemplo Canónico:
* **Precio de Lista Proveedor:** \$1.000,00
* **Bonificaciones:** `10+5+3`
  * Descuento equivalente: $1 - (0,90 \times 0,95 \times 0,97) = 17,065\%$ (mostrado como $17,07\%$).
  * **Neto bonificado:** $\$1.000,00 \times (1 - 0,17065) = \$829,35$.
* **Condiciones adicionales:**
  * Pronto pago: $2,0\%$
  * Flete: $3,5\%$
  * Percepción no recuperable: $1,5\%$
  * Impuestos internos: $0,0\%$
  * Factor neto: $1 - 0,02 + 0,035 + 0,015 = 1,03$ ($+3\%$).
* **Costo de Reposición Resultante:** $\$829,35 \times 1,03 =$ **\$854,23**.

En la ficha del proveedor (`product.supplierinfo`), el campo **Desglose** registra la auditoría legible:
> *Lista 1.000,00 → Neto 829,35 (10+5+3) → Reposición 854,23 (−2% PP +3,5% flete +1,5% percep.)*

---

## 3. Configuración y carga de condiciones

Las condiciones comerciales se gestionan de forma jerárquica y por empresa:

1. **Por Proveedor (`res.partner`):**
   * En la pestaña **Compra**, grupo **Condiciones comerciales**.
   * Campos dependientes de la empresa (`company_dependent=True`): cada razón social del grupo negocia sus propias condiciones.
   * `Bonificaciones` (texto, ej: `10+5+3` o `10+2,5`), `Pronto pago (%)`, `Flete (%)`, `Percepción no recuperable (%)`.
2. **Excepción por Ficha de Producto-Proveedor (`product.supplierinfo`):**
   * En la ficha de proveedor del producto, el tilde **Condiciones propias** permite anular las condiciones generales del proveedor para ese artículo específico y definir bonificaciones y porcentajes particulares.
   * Si no está tildado, hereda automáticamente las del proveedor principal vigente.
3. **Impuestos Internos (`product.category` y `product.template`):**
   * Se define un valor por defecto en la **Categoría de Producto**.
   * Se propaga automáticamente a los productos de dicha categoría, permitiendo su modificación manual por producto si fuera necesario.

---

## 4. Permisos de acceso

* **Solo los Gerentes de Compras (`purchase.group_purchase_manager`)** tienen permisos para editar los campos de condiciones comerciales (bonificaciones, pronto pago, flete, percepciones e impuestos internos).
* Para el resto de los usuarios (compradores estándar / `purchase.group_purchase_user`), los campos se presentan en modo solo lectura (`readonly="not can_edit_commercial_conditions"`).
* A nivel servidor, el mixin `commercial.conditions.access.mixin` bloquea intentos de modificación no autorizados levantando un `AccessError`.

---

## 5. Integración con Listas de Precios de Venta

El módulo agrega la opción **"Costo de Reposición"** en el selector de Base de cálculo de las reglas por fórmula en tarifas de venta:

1. Ir a **Ventas / Inventario → Tarifas de precios**.
2. Crear o editar una regla con método de cálculo **Fórmula**.
3. En el campo **Basado en**, seleccionar **Costo de Reposición**.
4. Definir el recargo objetivo deseado (ej. margen del 35% o recargo del 40%).
5. El precio de venta se calculará dinámicamente sobre el `replacement_cost` del producto. Si un producto aún no posee costo de reposición configurado, el sistema recurre de forma segura al costo estándar (`standard_price` / AVCO).

---

## 6. Comportamiento en Órdenes de Compra

* Al crear una orden de compra o agregar productos desde el catálogo:
  * El precio unitario (`price_unit`) toma el costo de referencia de catálogo del proveedor.
  * El campo **Descuento (%)** de la línea recibe automáticamente el porcentaje equivalente de las bonificaciones en cascada (ej. `17,07%`).
  * En la línea se registra el texto original de la cascada en el campo `discount_cascade` (ej. `10+5+3`).
* Si el comprador modifica manualmente el precio o el descuento, Odoo respeta la edición manual y no la sobreescribe (`technical_price_unit != price_unit`).
* **Nota:** Pronto pago, flete, percepciones e impuestos internos **no** se descuentan ni se agregan en la orden de compra, ya que la orden de compra refleja la facturación directa del proveedor.

---

## 7. Semáforo de Divergencia

El semáforo de divergencia heredado de `alpardata_purchase_reference_cost` se adapta automáticamente:
* El costo contable (AVCO / `standard_price`) proviene de recepciones valorizadas con facturas que ya tienen los descuentos comerciales aplicados.
* Por lo tanto, el semáforo ahora compara el AVCO contra el **Neto Bonificado (`net_purchase_cost`)**, evitando falsas alarmas de divergencia que antes se producían al comparar contra la lista bruta.

---

## 8. Limitaciones conocidas
* Los porcentajes deben encontrarse estrictamente en el rango $0 \le x < 100$ (no admite recargos negativos).
* No incluye fletes expresados como monto fijo por bulto/kilo (se modelan en este punto como porcentaje sobre el neto).
