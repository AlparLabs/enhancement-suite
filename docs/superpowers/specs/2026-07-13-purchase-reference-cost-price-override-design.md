# Costo de Referencia: pisar `price_unit` en compras + fix multiempresa

**Fecha:** 2026-07-13
**Módulo:** `alpardata_purchase_reference_cost`
**Versiones objetivo:** 18.0 y 19.0 (paridad)

## Contexto y problema

El módulo separa el costo contable (AVCO, `standard_price`) del costo comercial
(`reference_cost`). Hoy `reference_cost` en la línea de compra es un campo
`related` de solo lectura que **solo muestra** el valor, sin afectar el
`price_unit`.

Al proveedor se le comunica el **costo de referencia** (es lo que sale en el PDF
de la orden). Como el PDF calcula sobre `price_unit`, hoy hay una inconsistencia:
el `price_unit` lo pone Odoo desde el precio del proveedor/último costo, no desde
el costo de referencia.

Se detectaron dos problemas:

1. **Feature faltante:** al agregar un producto a la línea de compra, el
   `price_unit` debería tomar por defecto el costo de referencia
   correspondiente (editable, porque la factura final puede variar).
2. **Bug multiempresa:** el costo de referencia a veces no se refleja en la
   línea. El workaround manual era sacarle la "Empresa" al producto.

### Causa raíz del bug multiempresa

`product.template.reference_cost` es un campo `compute` con `store=True` cuyo
cómputo lee `self.env.company`
([product_template.py:57](../../../alpardata_purchase_reference_cost/models/product_template.py)).
Un campo almacenado guarda **un único valor** en la base, pero su cómputo depende
de la empresa activa → el valor persistido queda "pegado" a la última empresa que
lo recalculó. Además, el filtro `s.company_id == company` descarta el proveedor de
la empresa principal cuando se opera desde una sucursal (no hay fallback
jerárquico).

Este mismo campo alimenta las **listas de precios de venta**
([product_pricelist.py:53](../../../alpardata_purchase_reference_cost/models/product_pricelist.py)),
así que la inconsistencia también puede ensuciar precios de venta.

### Estructura multiempresa del entorno

- Hay **sucursales** configuradas como empresas hijas de una principal
  (`res.company.parent_id`).
- Hay también **empresas independientes** sin relación jerárquica, en el mismo
  entorno.
- Los costos de referencia se cargan generalmente en la **empresa principal**;
  ocasionalmente una sucursal tiene un precio propio distinto.

## Decisiones de diseño

- **Comportamiento del `price_unit`:** default editable (opción A). Al elegir el
  producto se autocompleta con el costo de referencia; el comprador puede
  modificarlo. La orden se emite con el de referencia; la factura final puede
  diferir.
- **Sin costo de referencia (0):** se respeta el comportamiento normal de Odoo
  (precio del proveedor / último costo).
- **`reference_cost` pasa a `store=False`** (no almacenado, `depends_context('company')`).
  - *Descartado:* `company_dependent=True` — combina mal con un campo computed
    desde `seller_ids`.
  - *Descartado:* dejarlo almacenado global y resolver empresa solo en el punto de
    uso — duplica lógica y no arregla las listas de precio.
- **La carga masiva NO se afecta:** importa a `product.supplierinfo.reference_cost`
  (float directo, almacenado). El campo del template es computed sin `inverse`, o
  sea nunca fue importable. Ninguna vista filtra/agrupa por él, así que `store=True`
  no aportaba nada.

## Diseño

### 1. `product_template.py` — `reference_cost` no almacenado + fallback jerárquico

- `reference_cost`: `store=False`, agregar `@api.depends_context('company')`.
- El cómputo arma una lista de preferencia de empresas recorriendo `parent_id`:
  **empresa actual → matriz → abuela → … → sin empresa (global)**.
- Candidatos: supplierinfo con `reference_cost > 0`, fechas vigentes
  (`date_start`/`date_end`), y `company_id` en esa cadena (o sin empresa).
- Orden de selección: **más específico primero** (menor índice en la cadena),
  desempate por `sequence`, luego `id`.
- Semántica multiempresa resultante:
  - **Sucursal:** ve sus propios supplierinfo; si no tiene, cae al de su matriz;
    si no, al global.
  - **Empresa independiente:** ve solo los propios + globales; nunca los de otra
    empresa.

Boceto:

```python
@api.depends(
    'seller_ids.reference_cost',
    'seller_ids.date_start',
    'seller_ids.date_end',
    'seller_ids.sequence',
    'seller_ids.company_id',
)
@api.depends_context('company')
def _compute_reference_cost(self):
    today = fields.Date.today()
    # Cadena de preferencia: empresa actual y sus matrices, más específico primero
    pref, comp = [], self.env.company
    while comp:
        pref.append(comp.id)
        comp = comp.parent_id
    rank = {cid: i for i, cid in enumerate(pref)}
    global_rank = len(pref)  # company_id=False rankea después de las específicas

    for tmpl in self:
        candidates = tmpl.seller_ids.filtered(
            lambda s: s.reference_cost > 0
            and (not s.date_start or s.date_start <= today)
            and (not s.date_end or s.date_end >= today)
            and (not s.company_id or s.company_id.id in rank)
        )
        def sort_key(s):
            r = rank.get(s.company_id.id, global_rank) if s.company_id else global_rank
            return (r, s.sequence, s.id)
        ordered = candidates.sorted(key=sort_key)
        tmpl.reference_cost = ordered[0].reference_cost if ordered else 0.0
```

*Nota:* verificar en implementación que `res.company.parent_id` es la relación de
jerarquía disponible en 18 y 19 (lo es en ambas).

### 2. `purchase_order_line.py` — pisar `price_unit` como default editable

- Override del compute de precio del core (nombre a confirmar:
  `_compute_price_unit_and_date_planned_and_name` en 18 y 19).
- Flujo: `super()` primero; luego, por cada línea con producto, resolver el costo
  de referencia bajo la empresa de la orden con
  `line.product_id.with_company(line.company_id).reference_cost`.
- Si `ref_cost > 0`: setear `line.price_unit` con conversión de moneda
  (empresa → moneda de la orden) usando el mismo patrón que
  [product_pricelist.py:66-71](../../../alpardata_purchase_reference_cost/models/product_pricelist.py).
- Si `ref_cost == 0`: no tocar (se respeta el precio de Odoo — opción A).
- Editable: como es un campo computed no almacenado del core, el valor queda
  editable; al cambiar cantidad/producto Odoo reprecia y se vuelve a aplicar el de
  referencia (consistente con Odoo).

Consideraciones:
- **Moneda:** mayormente ARS, pero puede haber compras en otra moneda → se incluye
  conversión `company.currency_id._convert(...)`.
- **UoM:** se asume que el costo de referencia está en la UoM del producto igual a
  la de la línea (caso común retail). Conversión de UoM queda fuera de alcance;
  documentar como limitación conocida.
- Respetar guardas del core: no tocar líneas con `invoice_lines`, ni sin producto.

### 3. Migraciones (18.0 y 19.0)

Al dejar de estar almacenado, se dropea la columna huérfana
`product_template.reference_cost`. El valor se recalcula desde los supplierinfo
(fuente de verdad) → no se pierde nada. Estrictamente Odoo tolera columnas
huérfanas, pero se dropea por higiene y para evitar confusión.

- **18.0:** bump de manifest `18.0.2.0.1` → `18.0.2.1.0` +
  `migrations/18.0.2.1.0/pre-migrate.py`.
- **19.0:** bump de manifest `19.0.2.0.0` → `19.0.2.1.0` +
  `migrations/19.0.2.1.0/pre-migrate.py`.
- Contenido de ambos pre-migrate: `DROP COLUMN IF EXISTS reference_cost` sobre
  `product_template` (guardando el patrón de logging existente y el early-return
  `if not version`).

### 4. Vistas

Sin cambios. El campo `reference_cost` ya se muestra en la línea de compra
([purchase_order_views.xml:11](../../../alpardata_purchase_reference_cost/views/purchase_order_views.xml))
y ahora reflejará el valor correcto por empresa.

## Contexto de la migración a 19.0 (referencia)

El error NOT NULL que se venía viendo en 19 provenía de
`migrations/19.0.2.0.0/pre-migrate.py`: creaba `product.supplierinfo` con `INSERT`
crudo sin poblar columnas obligatorias en Odoo 19 (p. ej. `currency_id`). Ya
resuelto en la rama `claude/19-migration-notnull-error-e000b6` cambiando la
estrategia a **`UPDATE`** del proveedor vigente en lugar de `INSERT`. Otros fixes
de compat 19 en esa rama: `privilege_id` en grupos de seguridad, quitar
`numbercall` del cron, `company_ids` en record rules, herencia de la vista de
ajustes. **Este spec no reabre eso**; solo lo documenta como contexto para que la
base 19 sobre la que se aplican estos cambios sea la correcta.

## Alcance / fuera de alcance

**En alcance:**
- `store=False` + fallback jerárquico en `product.template.reference_cost`.
- Override de `price_unit` en la línea de compra (default editable, con conversión
  de moneda).
- Migraciones drop-column en 18.0 y 19.0 con sus bumps de versión.

**Fuera de alcance:**
- Conversión de UoM del costo de referencia.
- Cambios en la lógica de importación masiva (ya cae en supplierinfo).
- Reabrir los fixes de migración 19.0 ya resueltos.

## Testing

- **Fallback jerárquico:** producto con supplierinfo solo en la principal; leer
  `reference_cost` desde una sucursal → debe traer el de la principal. Con un
  supplierinfo propio en la sucursal → debe ganar el de la sucursal. Desde una
  empresa independiente → no debe traer el de la principal.
- **`price_unit`:** agregar producto con costo de referencia a una OC → `price_unit`
  = costo de referencia; editable; con costo 0 → precio normal de Odoo.
- **Moneda:** OC en moneda distinta a la empresa → `price_unit` convertido.
- **Migración:** upgrade sobre base con columna existente → columna dropeada, sin
  pérdida de valores (se recomputan), sin errores.
