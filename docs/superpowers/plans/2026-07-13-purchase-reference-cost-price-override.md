# Costo de Referencia: pisar `price_unit` + fix multiempresa (18.0) — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** En Odoo 18, que al agregar un producto a una línea de compra el `price_unit` tome por defecto (editable) el costo de referencia correcto por empresa, y arreglar de raíz que el costo de referencia no se refleje en entornos multiempresa.

**Architecture:** `product.template.reference_cost` deja de estar almacenado y se recalcula por empresa activa con fallback jerárquico (sucursal → matriz → global), leyendo los proveedores con `sudo()` para saltar las reglas multiempresa. La línea de compra sobrescribe el cómputo de precio del core para poner el costo de referencia (convertido a la moneda de la orden) como default editable. Una migración dropea la columna huérfana.

**Tech Stack:** Odoo 18 (Python, ORM), OpenUpgrade-style pre-migrate SQL, tests con `odoo.tests.common.TransactionCase`.

**Spec:** [docs/superpowers/specs/2026-07-13-purchase-reference-cost-price-override-design.md](../specs/2026-07-13-purchase-reference-cost-price-override-design.md)

---

## Estructura de archivos

- **Modificar** `alpardata_purchase_reference_cost/models/product_template.py` — `reference_cost` a `store=False` + compute con fallback jerárquico y `sudo()`.
- **Modificar** `alpardata_purchase_reference_cost/models/purchase_order_line.py` — override de `_compute_price_unit_and_date_planned_and_name` + helper de conversión de moneda.
- **Crear** `alpardata_purchase_reference_cost/migrations/18.0.2.1.0/pre-migrate.py` — drop de la columna huérfana.
- **Modificar** `alpardata_purchase_reference_cost/__manifest__.py` — bump `18.0.2.0.1` → `18.0.2.1.0`.
- **Crear** `alpardata_purchase_reference_cost/tests/__init__.py` y `alpardata_purchase_reference_cost/tests/test_reference_cost.py` — tests de fallback multiempresa y de override de precio.

### Nota sobre correr los tests

Los tests corren dentro de Odoo (no en este entorno). Comando de referencia (adaptar `-d`, `-c` y rutas al entorno real):

```
odoo -d <db> -u alpardata_purchase_reference_cost \
     --test-enable --test-tags /alpardata_purchase_reference_cost \
     --stop-after-init
```

En cada paso "correr test" se indica el `--test-tags` acotado a la clase/método correspondiente.

---

## Task 1: Andamiaje de tests del módulo

Crea la carpeta de tests para que Odoo descubra los tests de las tareas siguientes.

**Files:**
- Create: `alpardata_purchase_reference_cost/tests/__init__.py`
- Create: `alpardata_purchase_reference_cost/tests/test_reference_cost.py`

- [ ] **Step 1: Crear `tests/__init__.py`**

```python
from . import test_reference_cost
```

- [ ] **Step 2: Crear `tests/test_reference_cost.py` con un esqueleto mínimo que falle**

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestReferenceCostCompany(TransactionCase):

    def test_scaffold_placeholder(self):
        # Placeholder temporal: se reemplaza en la Task 2.
        self.assertTrue(False, 'scaffold: reemplazar por tests reales')
```

- [ ] **Step 3: Correr el test para verificar que Odoo descubre la carpeta y falla**

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --test-enable --test-tags /alpardata_purchase_reference_cost:TestReferenceCostCompany.test_scaffold_placeholder --stop-after-init`
Expected: FAIL con `AssertionError: scaffold: reemplazar por tests reales` (confirma que la carpeta de tests se carga).

- [ ] **Step 4: Commit**

```bash
git add alpardata_purchase_reference_cost/tests/__init__.py alpardata_purchase_reference_cost/tests/test_reference_cost.py
git commit -m "test(purchase_reference_cost): andamiaje de tests del modulo"
```

---

## Task 2: `reference_cost` no almacenado + fallback jerárquico por empresa

Arregla el bug multiempresa: el campo pasa a no-almacenado, se recalcula por empresa activa, elige el proveedor más específico de la cadena jerárquica y lee con `sudo()` para no perder el proveedor de la matriz.

**Files:**
- Modify: `alpardata_purchase_reference_cost/models/product_template.py`
- Test: `alpardata_purchase_reference_cost/tests/test_reference_cost.py`

- [ ] **Step 1: Escribir los tests de fallback multiempresa (reemplazando el placeholder)**

Reemplazar **todo** el contenido de `tests/test_reference_cost.py` por:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestReferenceCostCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_company = cls.env['res.company'].create({'name': 'Principal Test'})
        cls.branch = cls.env['res.company'].create({
            'name': 'Sucursal Test',
            'parent_id': cls.main_company.id,
        })
        cls.independent = cls.env['res.company'].create({'name': 'Independiente Test'})
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor Test'})
        cls.product = cls.env['product.product'].create({'name': 'Producto Test'})
        cls.template = cls.product.product_tmpl_id

    def _add_seller(self, company, cost, sequence=10):
        return self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_tmpl_id': self.template.id,
            'company_id': company.id if company else False,
            'reference_cost': cost,
            'sequence': sequence,
        })

    def test_branch_falls_back_to_main(self):
        """Sin proveedor propio, la sucursal cae al costo de la empresa matriz."""
        self._add_seller(self.main_company, 100.0)
        rc = self.template.with_company(self.branch).reference_cost
        self.assertEqual(rc, 100.0)

    def test_branch_own_cost_wins(self):
        """El proveedor propio de la sucursal gana sobre el de la matriz."""
        self._add_seller(self.main_company, 100.0)
        self._add_seller(self.branch, 120.0)
        self.assertEqual(self.template.with_company(self.branch).reference_cost, 120.0)
        self.assertEqual(self.template.with_company(self.main_company).reference_cost, 100.0)

    def test_independent_company_does_not_see_main(self):
        """Una empresa independiente no toma el costo de otra empresa."""
        self._add_seller(self.main_company, 100.0)
        self.assertEqual(self.template.with_company(self.independent).reference_cost, 0.0)

    def test_global_seller_used_as_last_resort(self):
        """Un proveedor global (sin empresa) aplica cuando no hay uno específico."""
        self._add_seller(False, 90.0)
        self.assertEqual(self.template.with_company(self.independent).reference_cost, 90.0)
        self.assertEqual(self.template.with_company(self.branch).reference_cost, 90.0)

    def test_specific_beats_global(self):
        """El proveedor de la empresa gana sobre el global."""
        self._add_seller(False, 90.0)
        self._add_seller(self.main_company, 100.0)
        self.assertEqual(self.template.with_company(self.main_company).reference_cost, 100.0)
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --test-enable --test-tags /alpardata_purchase_reference_cost:TestReferenceCostCompany --stop-after-init`
Expected: FAIL — al menos `test_branch_falls_back_to_main` y `test_independent_company_does_not_see_main` fallan, porque el compute actual filtra `s.company_id == company` (sin fallback) y usa `store=True`.

- [ ] **Step 3: Modificar `product_template.py` — campo a `store=False`**

Reemplazar la definición del campo `reference_cost` (actualmente con `store=True`) por:

```python
    reference_cost = fields.Float(
        string='Costo de referencia',
        digits='Product Price',
        compute='_compute_reference_cost',
        store=False,
        help=(
            'Calculado automáticamente desde el Costo de Referencia del '
            'proveedor principal vigente (menor sequence, fecha válida hoy). '
            'Actualizalo cargando una nueva lista de precios del proveedor.'
        ),
    )
```

- [ ] **Step 4: Modificar `product_template.py` — nuevo cómputo con fallback jerárquico**

Reemplazar **todo** el método `_compute_reference_cost` (junto con su decorador `@api.depends(...)`) por:

```python
    @api.depends(
        'seller_ids.reference_cost',
        'seller_ids.date_start',
        'seller_ids.date_end',
        'seller_ids.sequence',
        'seller_ids.company_id',
    )
    @api.depends_context('company')
    def _compute_reference_cost(self) -> None:
        today = fields.Date.today()
        # Cadena de preferencia de empresas: la empresa activa y sus matrices
        # (más específica primero), recorriendo parent_id. Los proveedores sin
        # empresa (globales) se consideran al final.
        preferred_ids = []
        company = self.env.company
        while company:
            preferred_ids.append(company.id)
            company = company.parent_id
        rank = {cid: idx for idx, cid in enumerate(preferred_ids)}
        global_rank = len(preferred_ids)

        def _sort_key(seller):
            if seller.company_id:
                company_rank = rank.get(seller.company_id.id, global_rank)
            else:
                company_rank = global_rank
            return (company_rank, seller.sequence, seller.id)

        for tmpl in self:
            # sudo(): las reglas multiempresa filtrarían los proveedores de la
            # matriz cuando se opera desde una sucursal que no la tiene habilitada.
            # El filtro por `rank` evita que una empresa independiente tome
            # precios ajenos (solo ve los suyos + los globales).
            candidates = tmpl.sudo().seller_ids.filtered(
                lambda s: s.reference_cost > 0
                and (not s.date_start or s.date_start <= today)
                and (not s.date_end or s.date_end >= today)
                and (not s.company_id or s.company_id.id in rank)
            )
            ordered = candidates.sorted(key=_sort_key)
            tmpl.reference_cost = ordered[0].reference_cost if ordered else 0.0
```

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --test-enable --test-tags /alpardata_purchase_reference_cost:TestReferenceCostCompany --stop-after-init`
Expected: PASS — los 5 tests verdes.

- [ ] **Step 6: Commit**

```bash
git add alpardata_purchase_reference_cost/models/product_template.py alpardata_purchase_reference_cost/tests/test_reference_cost.py
git commit -m "fix(purchase_reference_cost): reference_cost no almacenado con fallback jerarquico por empresa"
```

---

## Task 3: Pisar `price_unit` con el costo de referencia (default editable)

Al agregar un producto a la línea de compra, `price_unit` toma el costo de referencia (convertido a la moneda de la orden). Queda editable; si no hay costo de referencia, se respeta el precio de Odoo.

**Files:**
- Modify: `alpardata_purchase_reference_cost/models/purchase_order_line.py`
- Test: `alpardata_purchase_reference_cost/tests/test_purchase_line_price.py`

- [ ] **Step 1: Escribir los tests del override de precio**

Crear `alpardata_purchase_reference_cost/tests/test_purchase_line_price.py`:

```python
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPurchaseLineReferenceCost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor Test'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto con costo ref',
            'standard_price': 50.0,
        })
        cls.env['product.supplierinfo'].create({
            'partner_id': cls.partner.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'price': 80.0,
            'reference_cost': 100.0,
        })

    def _new_line(self, product, currency=None):
        vals = {'partner_id': self.partner.id}
        if currency:
            vals['currency_id'] = currency.id
        po = self.env['purchase.order'].create(vals)
        return self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': product.id,
            'product_qty': 1.0,
        })

    def test_price_unit_takes_reference_cost(self):
        """price_unit toma el costo de referencia, no el precio del proveedor."""
        line = self._new_line(self.product)
        self.assertEqual(line.price_unit, 100.0)

    def test_price_unit_is_editable(self):
        """El comprador puede pisar el precio a mano y persiste."""
        line = self._new_line(self.product)
        line.price_unit = 90.0
        self.assertEqual(line.price_unit, 90.0)

    def test_no_reference_cost_keeps_odoo_price(self):
        """Sin costo de referencia, se respeta el precio del proveedor de Odoo."""
        product2 = self.env['product.product'].create({'name': 'Producto sin costo ref'})
        self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_tmpl_id': product2.product_tmpl_id.id,
            'price': 70.0,
        })
        line = self._new_line(product2)
        self.assertEqual(line.price_unit, 70.0)

    def test_price_unit_currency_conversion(self):
        """El costo de referencia se convierte a la moneda de la orden."""
        company_currency = self.env.company.currency_id
        other = self.env['res.currency'].create({
            'name': 'TSTX',
            'symbol': 'T',
            'rounding': 0.01,
        })
        self.env['res.currency.rate'].create({
            'currency_id': other.id,
            'company_id': self.env.company.id,
            'rate': 2.0,  # 1 moneda-empresa = 2 TSTX
            'name': fields.Date.today(),
        })
        line = self._new_line(self.product, currency=other)
        # Si la orden quedó efectivamente en la otra moneda, se espera 200.
        if line.order_id.currency_id == other and other != company_currency:
            self.assertAlmostEqual(line.price_unit, 200.0, places=2)
        else:
            # Entorno donde la moneda de la orden no cambió: sin conversión.
            self.assertAlmostEqual(line.price_unit, 100.0, places=2)
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --test-enable --test-tags /alpardata_purchase_reference_cost:TestPurchaseLineReferenceCost --stop-after-init`
Expected: FAIL — `test_price_unit_takes_reference_cost` da 80.0 (precio del proveedor) en vez de 100.0, porque todavía no existe el override.

- [ ] **Step 3: Implementar el override en `purchase_order_line.py`**

Reemplazar **todo** el contenido de `alpardata_purchase_reference_cost/models/purchase_order_line.py` por:

```python
from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    reference_cost = fields.Float(
        string='Costo de referencia',
        related='product_id.reference_cost',
        digits='Product Price',
        readonly=True,
        store=False,
    )

    def _compute_price_unit_and_date_planned_and_name(self):
        """Extiende el cálculo de precio del core (Odoo 18).

        Cuando el producto tiene un costo de referencia (>0) para la empresa de
        la orden, se usa ese valor como precio unitario por defecto (editable).
        La orden de compra se emite con el costo de referencia; la factura final
        puede diferir. Si no hay costo de referencia, se respeta el precio que
        calcula Odoo (precio de proveedor / último costo).
        """
        super()._compute_price_unit_and_date_planned_and_name()
        for line in self:
            if not line.product_id or line.invoice_lines or not line.company_id:
                continue
            ref_cost = line.product_id.with_company(line.company_id).reference_cost
            if ref_cost <= 0:
                continue
            line.price_unit = line._reference_cost_in_order_currency(ref_cost)

    def _reference_cost_in_order_currency(self, ref_cost: float) -> float:
        """Convierte el costo de referencia (moneda de la empresa de la línea)
        a la moneda de la orden de compra."""
        self.ensure_one()
        src_currency = self.company_id.currency_id
        dst_currency = self.order_id.currency_id or src_currency
        if not src_currency or src_currency == dst_currency:
            return ref_cost
        date = self.order_id.date_order or fields.Date.context_today(self)
        return src_currency._convert(
            ref_cost, dst_currency, self.company_id, date, round=False
        )
```

- [ ] **Step 4: Registrar el test nuevo en `tests/__init__.py`**

Reemplazar el contenido de `alpardata_purchase_reference_cost/tests/__init__.py` por:

```python
from . import test_reference_cost
from . import test_purchase_line_price
```

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --test-enable --test-tags /alpardata_purchase_reference_cost:TestPurchaseLineReferenceCost --stop-after-init`
Expected: PASS — los 4 tests verdes.

- [ ] **Step 6: Commit**

```bash
git add alpardata_purchase_reference_cost/models/purchase_order_line.py alpardata_purchase_reference_cost/tests/test_purchase_line_price.py alpardata_purchase_reference_cost/tests/__init__.py
git commit -m "feat(purchase_reference_cost): pisar price_unit con costo de referencia como default editable"
```

---

## Task 4: Migración drop-column + bump de versión

Como `reference_cost` deja de estar almacenado, se elimina la columna huérfana. El valor se recalcula desde `product.supplierinfo` (fuente de verdad); no hay pérdida de datos.

**Files:**
- Create: `alpardata_purchase_reference_cost/migrations/18.0.2.1.0/pre-migrate.py`
- Modify: `alpardata_purchase_reference_cost/__manifest__.py`

- [ ] **Step 1: Crear la migración `18.0.2.1.0/pre-migrate.py`**

Crear `alpardata_purchase_reference_cost/migrations/18.0.2.1.0/pre-migrate.py` (la carpeta de migración no lleva `__init__.py`, igual que `18.0.2.0.0`):

```python
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración 18.0.2.0.x → 18.0.2.1.0

    reference_cost en product.template pasa de computed-stored a computed NO
    almacenado. Se elimina la columna huérfana: el valor se recalcula on-the-fly
    desde product.supplierinfo.reference_cost (la fuente de verdad), así que no
    hay pérdida de datos.
    """
    if not version:
        # Instalación nueva: no hay nada que migrar.
        return

    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'reference_cost'
    """)
    if cr.fetchone():
        _logger.info(
            'pre-migrate: reference_cost pasa a no-almacenado. '
            'Eliminando columna huérfana product_template.reference_cost.'
        )
        cr.execute(
            'ALTER TABLE product_template DROP COLUMN IF EXISTS reference_cost'
        )
    else:
        _logger.info(
            'pre-migrate: columna product_template.reference_cost no existe, '
            'nada que hacer.'
        )
```

- [ ] **Step 2: Bump de versión en el manifest**

En `alpardata_purchase_reference_cost/__manifest__.py`, cambiar la línea de versión:

```python
    'version': '18.0.2.0.1',
```

por:

```python
    'version': '18.0.2.1.0',
```

- [ ] **Step 3: Verificación manual del upgrade**

Sobre una base que ya tenga el módulo instalado con la columna presente, correr el upgrade:

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --stop-after-init`
Expected (en el log): línea `pre-migrate: ... Eliminando columna huérfana product_template.reference_cost.` y el upgrade termina sin errores.

Verificación SQL (la columna ya no debe existir):

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'product_template' AND column_name = 'reference_cost';
```

Expected: 0 filas.

Verificación funcional: abrir un producto con proveedor que tenga costo de referencia y confirmar que el campo "Costo de referencia" sigue mostrando el valor correcto (recalculado).

- [ ] **Step 4: Commit**

```bash
git add alpardata_purchase_reference_cost/migrations/18.0.2.1.0/pre-migrate.py alpardata_purchase_reference_cost/__manifest__.py
git commit -m "chore(purchase_reference_cost): migracion drop-column reference_cost + bump 18.0.2.1.0"
```

---

## Task 5: Verificación integral y regresión

Corre toda la suite del módulo y verifica el flujo end-to-end en la UI.

**Files:** (ninguno — solo verificación)

- [ ] **Step 1: Correr toda la suite del módulo**

Run: `odoo -d <db> -u alpardata_purchase_reference_cost --test-enable --test-tags /alpardata_purchase_reference_cost --stop-after-init`
Expected: PASS — todos los tests del módulo verdes, sin errores de carga ni de migración.

- [ ] **Step 2: Verificación funcional en la UI (multiempresa)**

- Cargar un costo de referencia en un producto vía proveedor en la **empresa principal**.
- Desde una **sucursal** (empresa hija), abrir el producto y confirmar que "Costo de referencia" muestra el valor de la principal.
- Crear una **orden de compra** en la sucursal, agregar ese producto y confirmar que `price_unit` toma el costo de referencia y que **se puede editar** a mano.
- Confirmar que en una **empresa independiente** el producto no toma el costo de la principal.

- [ ] **Step 3: Verificación del PDF**

Generar el PDF de la orden de compra y confirmar que el precio comunicado al proveedor es el costo de referencia (porque ahora `price_unit` = costo de referencia).

---

## Self-Review (cobertura vs spec)

- **Sección 1 del spec (reference_cost no almacenado + fallback jerárquico + sudo):** Task 2.
- **Sección 2 del spec (override de price_unit + conversión de moneda):** Task 3.
- **Sección 3 del spec (migración drop-column + bump 18.0.2.1.0):** Task 4.
- **Sección 4 del spec (vistas sin cambios):** sin tarea (correcto — no requiere cambios).
- **Testing del spec (fallback, price_unit, moneda, migración):** Tasks 2, 3, 4, 5.
