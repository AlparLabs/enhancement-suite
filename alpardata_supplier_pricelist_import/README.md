# AlparData - Importador de Listas de Proveedores (`alpardata_supplier_pricelist_import`)

Módulo para Odoo 19.0 desarrollado por AlparData.  
Punto 2 del roadmap de costo comercial para retail en Argentina (extiende `alpardata_purchase_replacement_cost`).

---

## 1. Problema que resuelve

En empresas de retail y distribución, los proveedores actualizan sus listas de precios periódicamente con catálogos que contienen miles de artículos en formatos heterogéneos (Excel `.xlsx`, `.xls` o `.csv` delimitados por coma o punto y coma, con precios con o sin IVA, o simplemente comunicando aumentos porcentuales generales por categoría).

Cargar o actualizar estas listas a mano en Odoo es inviable y riesgoso:
1. No se puede previsualizar el impacto económico antes de impactar los costos.
2. Es difícil auditar qué productos cambiaron, cuáles mantuvieron su precio y cuáles no se encontraron.
3. Se pierde la trazabilidad histórica de vigencias y costos si se sobreescriben las fichas de proveedor.

Este módulo introduce un **Importador de Listas de Proveedores** con:
* **Perfiles de importación configurables por proveedor** (mapeo por nombre de columna, no por índice).
* **Doble modo:** Carga desde archivo (.xlsx, .xls, .csv) o Aumento porcentual masivo.
* **Vista previa exhaustiva** antes de aplicar, con cálculo en tiempo real de la variación porcentual y el nuevo costo de reposición (`replacement_cost`).
* **Vigencia programable y trazabilidad:** crea nuevas fichas de `product.supplierinfo` con vigencia desde la fecha indicada, cerrando automáticamente las anteriores y registrando el historial con el número de importación.

---

## 2. Perfiles de Importación (`supplier.pricelist.import.profile`)

Cada proveedor suele enviar sus listas en un formato propio. El perfil permite configurar una sola vez las reglas de lectura:

* **Proveedor y Empresa:** Asociado al proveedor específico y multi-compañía.
* **Tipo de archivo:** Excel (`.xlsx`, `.xls`) o `CSV`.
* **Configuración de lectura:**
  * **Fila de encabezados (`header_row`):** Indica en qué fila comienzan los títulos (por defecto fila 1). Útil cuando el proveedor incluye logos o metadatos en las primeras filas.
  * **Hoja (`sheet_name`):** Nombre de la hoja de cálculo a leer en archivos Excel (opcional; si está vacío, lee la primera hoja activa).
  * **Delimitador y Codificación CSV:** Delimitador (`,`, `;`, tabulación) y codificación (`utf-8`, `latin1`, `windows-1252`).
  * **Separador decimal:** Coma `,` o punto `.` para parsear precios correctamente.
* **Columnas mapeadas (por nombre de encabezado):**
  * `Columna de Código`: Nombre del encabezado que contiene el código de producto (busca por código de proveedor en `product.supplierinfo`, código interno `default_code` o código de barras `barcode`).
  * `Columna de Precio`: Nombre del encabezado con el precio de lista.
  * `Columna de Bonificación (opcional)`: Nombre del encabezado con la bonificación en cascada (ej: `10+5+3`).
  * *La comparación es insensible a mayúsculas, tildes y espacios extras.*
* **Tratamiento de IVA:**
  * Si el proveedor envía precios finales con IVA (`price_includes_vat`), se configura el porcentaje de alícuota a descontar (ej. 21% o 10.5%) para registrar el precio neto de lista en Odoo.

---

## 3. Modos de Importación

### Modo A: Archivo del Proveedor (`mode='file'`)
1. Se selecciona el proveedor y el perfil configurado.
2. Se adjunta el archivo provisto por el proveedor (.xlsx, .xls o .csv).
3. Se define la fecha de vigencia (`effective_date`).
4. Se presiona **Generar vista previa**. El sistema procesa el archivo fila por fila sin modificar aún la base de datos.

### Modo B: Aumento Porcentual (`mode='percent'`)
1. Se selecciona el proveedor y se ingresa el porcentaje de variación (positivo para aumentos, ej: `12.5`, o negativo para bajas, ej: `-5`).
2. Se pueden aplicar filtros opcionales por **Categorías de producto** (incluye recursivamente subcategorías) y **Etiquetas de producto**.
3. Se define la fecha de vigencia (`effective_date`).
4. Se presiona **Generar vista previa**. El sistema busca las fichas vigentes del proveedor que cumplan los criterios y proyecta los nuevos valores.

---

## 4. Vista Previa y Edición Interactiva

Al generar la vista previa, se analizan todas las líneas y se clasifican:

| Estado (`status`) | Significado | Comportamiento |
| :--- | :--- | :--- |
| **`change`** | El precio o la bonificación difieren del valor vigente. | Se marca con tilde `to_apply = True` por defecto. El usuario puede desmarcar artículos específicos si no desea aplicar el cambio. |
| **`unchanged`** | El precio y bonificación son idénticos a los vigentes. | `to_apply = False`. Fila atenuada en gris. |
| **`not_found`** | El código no coincide con ningún producto ni ficha del proveedor. | `to_apply = False`. Alerta visual para auditoría. |
| **`error`** | Fila con precio inválido, código duplicado o cascada malformada. | `to_apply = False`. Alerta en rojo con mensaje descriptivo. |

En cada línea se visualiza:
* Código y Producto (`product.template`).
* Precio de lista actual vs nuevo precio de lista.
* Variación porcentual (`%`) resaltada con colores.
* Bonificación actual vs nueva bonificación.
* Costo de reposición anterior vs nuevo costo de reposición proyectado.

---

## 5. Aplicación y Cierre de Vigencias

Al presionar el botón **Aplicar** (requiere confirmación):
1. Se toman todas las líneas con `status == 'change'` que mantengan la casilla `to_apply` tildada.
2. Se crean en lote nuevos registros de `product.supplierinfo` con:
   * `date_start = effective_date`.
   * Nuevo `reference_cost`.
   * Si cambió la bonificación, se activa `use_own_conditions = True` y se asigna la nueva cascada, conservando los porcentajes de pronto pago, flete y percepciones del proveedor.
3. El módulo base `alpardata_purchase_reference_cost` intercepta la creación y:
   * Cierra automáticamente la vigencia anterior fijando `date_end = effective_date - 1 día`.
   * Genera el registro de auditoría en `product.supplierinfo.cost.history` con el motivo `Importación <NÚMERO>`.
4. La importación pasa al estado **Aplicada (`done`)** y queda bloqueada para modificaciones.
5. Se publica un mensaje en el chatter resumiendo la cantidad de fichas actualizadas, omitidas, no encontradas y con error.

---

## 6. Permisos de Acceso

* **Compradores (`purchase.group_purchase_user`):**
  * Pueden ver el menú de importaciones y el botón inteligente en la ficha del proveedor.
  * Pueden crear borradores de importación, cargar archivos y generar vistas previas.
  * No pueden modificar perfiles de importación ni aplicar listas.
* **Gerentes de Compras (`purchase.group_purchase_manager`):**
  * Acceso completo para crear y editar perfiles de importación en **Compras → Configuración → Perfiles de listas de proveedores**.
  * Autorización exclusiva para ejecutar la acción **Aplicar** en las importaciones.

---

## 7. Limitaciones y Consideraciones Técnicas

* **No crea productos inexistentes:** Si un proveedor incluye artículos nuevos en su catálogo que aún no han sido dados de alta en Odoo, la línea se clasifica como `not_found` con el número de fila correspondiente. Los productos deben crearse previamente en el catálogo para ser vinculados.
* **Identificación de columnas:** Se realiza por comparación normalizada del texto de los encabezados (sin tildes, minúsculas, espacios colapsados). No depende del orden ni la posición de las columnas.
* **Dependencias externas:** Requiere la librería Python `openpyxl` (declarada en `external_dependencies`) para procesar archivos Microsoft Excel (.xlsx).
