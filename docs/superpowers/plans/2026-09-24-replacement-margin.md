# Margen de Reposición en POS — Plan de implementación

> **Para agentes:** implementar tarea por tarea, en orden. Cada paso usa checkbox (`- [ ]`).
> Si usás superpowers: REQUIRED SUB-SKILL `superpowers:subagent-driven-development` o
> `superpowers:executing-plans`.

**Goal:** Crear `alpardata_pos_replacement_margin`: guardar en cada línea de POS el costo
de reposición unitario al momento de la venta y calcular el margen de reposición,
disponible en la orden y en el análisis de POS junto al margen estándar.

**Architecture:** Un módulo que depende de `point_of_sale` y de `alpardata_replenishment_cost`
(punto 1, sobre Adhoc). El costo sale de `replenishment_cost` de Adhoc (fallback AVCO) y
se fija en campos computados almacenados al sincronizar la orden. El reporte SQL
`report.pos.order` suma el margen con la misma expresión que el margen estándar. La parte
de ventas no se desarrolla: la cubre `product_replenishment_cost_sale_margin` de Adhoc.

**Tech Stack:** Odoo 19.0 (`point_of_sale`), Adhoc `product_replenishment_cost`.

**Spec:** `docs/superpowers/specs/2026-09-24-replacement-margin-design.md`
**Requisito previo:** punto 1 (`alpardata_replenishment_cost`) mergeado en `19.0`.
**Actualizado a Adhoc:** 2026-09-24. Reemplaza la versión con dos módulos (ventas y POS).

---

## Convenciones

- **Rama:** `feat/pos-replacement-margin` desde `19.0`.
- Strings y commits en castellano: `feat(pos_replacement_margin): ...`.
- **Odoo 19:** `<list>`, `invisible="expr"`, `column_invisible` en columnas de listas.
- **Addons path:** además de `enhancement-suite`, `AlparLabs/product` rama `19.0` (Adhoc).
- Fuente de Odoo: `C:\Users\Santiago\Desktop\Odoo\odoo-19.0` — mirar
  `addons/point_of_sale/models/pos_order.py` (`PosOrderLine`, `_compute_margin`) y
  `addons/point_of_sale/tests/test_pos_margin.py` antes de empezar: este plan copia sus
  patrones.
- **Tests:**

  ```bash
  odoo-bin -c odoo.conf -d odoo19_dev -i alpardata_pos_replacement_margin --test-enable --test-tags /alpardata_pos_replacement_margin --stop-after-init --log-level=test
  ```

## Mapa de archivos (nuevo, bajo `alpardata_pos_replacement_margin/`)

- `__init__.py` (con `pre_init_hook`), `__manifest__.py`, `README.md`
- `models/__init__.py`, `models/product_product.py`, `models/pos_order.py`
- `report/__init__.py`, `report/pos_order_report.py`
- `views/pos_order_views.xml`
- `tests/__init__.py`, `tests/test_pos_replacement_margin.py`

---

### Tarea 1: Esqueleto, costo unitario y margen en líneas y órdenes

**Files:** Create el esqueleto, `models/product_product.py`, `models/pos_order.py`,
`tests/test_pos_replacement_margin.py`.

- [ ] **Paso 1: `__init__.py`** — el `pre_init_hook` crea las columnas vacías **antes**
de instalar, para que el ORM no recalcule las órdenes históricas con el costo de hoy:

```python
from . import models
from . import report


def pre_init_hook(env):
    """Crea las columnas en 0: las órdenes anteriores a la instalación no se
    recalculan (quedarían con el costo de hoy, que es el dato engañoso)."""
    env.cr.execute("""
        ALTER TABLE pos_order_line
            ADD COLUMN IF NOT EXISTS replacement_cost_unit double precision DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replacement_margin numeric DEFAULT 0;
        ALTER TABLE pos_order
            ADD COLUMN IF NOT EXISTS replacement_margin numeric DEFAULT 0;
    """)
```

`__manifest__.py`:

```python
{
    'name': 'AlparData - Margen de Reposición en POS',
    'version': '19.0.1.0.0',
    'summary': 'Margen del punto de venta calculado contra el costo de reposición',
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Sales/Point of Sale',
    'license': 'AGPL-3',
    'depends': ['point_of_sale', 'alpardata_replenishment_cost'],
    'data': [],  # la tarea 3 agrega las vistas
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

`models/__init__.py`:

```python
from . import product_product
from . import pos_order
```

`report/__init__.py`: `# from . import pos_order_report` —
`tests/__init__.py`: `from . import test_pos_replacement_margin`

- [ ] **Paso 2: test que falla** — `tests/test_pos_replacement_margin.py`

```python
from __future__ import annotations

import odoo
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@odoo.tests.tagged('post_install', '-at_install')
class TestPosReplacementMargin(TestPoSCommon):

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        rule_10 = self.env['product.replenishment_cost.rule'].create({
            'name': 'Bonif 10 POS',
            'item_ids': [(0, 0, {'name': 'b1', 'percentage_amount': -10.0})],
        })
        vendor = self.env['res.partner'].create({
            'name': 'Proveedor POS', 'replenishment_cost_rule_id': rule_10.id,
        })
        # precio 10, AVCO 5, lista 6 con bonificación 10 % → reposición 5,40
        self.product = self.create_product('Galletitas', self.categ_basic, 10, 5)
        self.product.replenishment_cost_type = 'supplier_price'
        self.env['product.supplierinfo'].create({
            'partner_id': vendor.id,
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'price': 6.0,
        })
        self.no_list = self.create_product('Sin lista', self.categ_basic, 10, 5)

    def _sync(self, lines):
        self.open_new_session()
        self.env['pos.order'].sync_from_ui([self.create_ui_order_data(lines)])
        return self.pos_session.order_ids[0]

    def test_sale(self):
        order = self._sync([(self.product, 2)])
        line = order.lines
        self.assertAlmostEqual(line.replacement_cost_unit, 5.4, places=4)
        self.assertAlmostEqual(line.replacement_margin, 20.0 - 10.8, places=4)
        self.assertAlmostEqual(order.replacement_margin, 9.2, places=4)

    def test_refund_is_negative(self):
        order = self._sync([(self.product, -1)])
        self.assertAlmostEqual(order.lines.replacement_margin, -10.0 + 5.4, places=4)

    def test_fallback_to_avco(self):
        order = self._sync([(self.no_list, 1)])
        self.assertAlmostEqual(order.lines.replacement_cost_unit, 5.0, places=4)
```

> Si `create_ui_order_data` no acepta cantidades negativas para simular una devolución,
> usar el flujo de devolución de `odoo-19.0/addons/point_of_sale/tests/test_pos_margin.py`.
> Si `create_product` crea el producto en otra empresa que la del POS, la ficha de
> proveedor global (sin empresa) igual aplica.

- [ ] **Paso 3: correr** → falla.

- [ ] **Paso 4: `models/product_product.py`**

```python
from __future__ import annotations

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _pos_replenishment_cost(self, company, currency, date=None) -> float:
        """Costo de reposición unitario (UoM del producto) en `currency`: el de Adhoc
        en `company`, o el costo contable si no hay costo de reposición."""
        self.ensure_one()
        product = self.with_company(company)
        cost = product.replenishment_cost or product.standard_price
        if currency and currency != company.currency_id:
            cost = company.currency_id._convert(
                cost, currency, company, date or fields.Date.today(), round=False,
            )
        return cost
```

- [ ] **Paso 5: `models/pos_order.py`**

```python
from __future__ import annotations

from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    replacement_cost_unit = fields.Float(
        string='Costo de reposición',
        compute='_compute_replacement_cost_unit',
        store=True,
        min_display_digits='Product Price',
        help='Costo de reposición unitario al sincronizar la orden.',
    )
    replacement_margin = fields.Monetary(
        string='Margen de reposición',
        compute='_compute_replacement_margin',
        store=True,
    )

    @api.depends('product_id', 'order_id.company_id', 'order_id.currency_id')
    def _compute_replacement_cost_unit(self) -> None:
        for line in self:
            order = line.order_id
            if not line.product_id or line.product_id.type == 'combo' or not order:
                line.replacement_cost_unit = 0.0
                continue
            company = order.company_id
            line.replacement_cost_unit = line.product_id._pos_replenishment_cost(
                company,
                order.currency_id or company.currency_id,
                fields.Date.to_date(order.date_order or fields.Datetime.now()),
            )

    @api.depends('price_subtotal', 'qty', 'replacement_cost_unit')
    def _compute_replacement_margin(self) -> None:
        for line in self:
            line.replacement_margin = line.price_subtotal - line.replacement_cost_unit * line.qty


class PosOrder(models.Model):
    _inherit = 'pos.order'

    replacement_margin = fields.Monetary(
        string='Margen de reposición',
        compute='_compute_replacement_margin',
        store=True,
    )

    @api.depends('lines.replacement_margin')
    def _compute_replacement_margin(self) -> None:
        for order in self:
            order.replacement_margin = sum(order.lines.mapped('replacement_margin'))
```

> `pos.order.line` tiene `currency_id` (related a la orden), por eso `Monetary` funciona
> sin declarar `currency_field`. Verificarlo en `pos_order.py` (`class PosOrderLine`).

- [ ] **Paso 6: correr** → los tres tests pasan.

- [ ] **Paso 7: commit**

```bash
git add alpardata_pos_replacement_margin
git commit -m "feat(pos_replacement_margin): costo y margen de reposición en órdenes de POS"
```

---

### Tarea 2: Análisis de POS

**Files:** Create `report/pos_order_report.py`; Modify `tests/test_pos_replacement_margin.py`.

- [ ] **Paso 1: agregar test** a la clase:

```python
    def test_report(self):
        order = self._sync([(self.product, 2)])
        self.env.flush_all()
        data = self.env['report.pos.order']._read_group(
            [('order_id', '=', order.id)], [], ['replacement_margin:sum'],
        )
        self.assertAlmostEqual(data[0][0], 9.2, places=2)
```

- [ ] **Paso 2: `report/pos_order_report.py`**

```python
from __future__ import annotations

from odoo import fields, models


class ReportPosOrder(models.Model):
    _inherit = 'report.pos.order'

    replacement_margin = fields.Float(string='Margen de reposición', readonly=True)

    def _select(self):
        # Misma conversión de moneda que el campo `margin` del reporte estándar.
        return super()._select() + """,
                l.replacement_margin / COALESCE(NULLIF(s.currency_rate, 0), 1.0) AS replacement_margin
        """
```

Descomentar en `report/__init__.py`.

> `_select()` del core termina en `fpc.id AS pos_categ_id` sin coma final; por eso se
> agrega `,` al principio. Si en tu versión `_select` termina distinto, abrir
> `odoo-19.0/addons/point_of_sale/report/pos_order_report.py` y ajustar.

- [ ] **Paso 3: correr** → `test_report` pasa.

- [ ] **Paso 4: commit**

```bash
git add alpardata_pos_replacement_margin
git commit -m "feat(pos_replacement_margin): margen de reposición en el análisis de POS"
```

---

### Tarea 3: Vistas

- [ ] **Paso 1: `views/pos_order_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_pos_pos_form_replacement_margin" model="ir.ui.view">
        <field name="name">pos.order.form.replacement.margin</field>
        <field name="model">pos.order</field>
        <field name="inherit_id" ref="point_of_sale.view_pos_pos_form"/>
        <field name="arch" type="xml">
            <xpath expr="//label[@for='margin']" position="before">
                <field name="replacement_margin"/>
            </xpath>
            <xpath expr="//field[@name='lines']//list//field[@name='margin']" position="after">
                <field name="replacement_cost_unit" optional="hide"/>
                <field name="replacement_margin" optional="hide" widget="monetary"/>
            </xpath>
        </field>
    </record>
</odoo>
```

> Verificar en `odoo-19.0/addons/point_of_sale/views/pos_order_view.xml` que el
> `<label for="margin"/>` y la lista de `lines` con `margin` estén donde se ancla (cerca
> de las líneas 96 y 142).

- [ ] **Paso 2: manifest** `'data': ['views/pos_order_views.xml'],`

- [ ] **Paso 3: actualizar y correr todos los tests** → 0 fallas.

- [ ] **Paso 4: commit**

```bash
git add alpardata_pos_replacement_margin
git commit -m "feat(pos_replacement_margin): vistas de orden de POS"
```

---

### Tarea 4: README, instalación con datos y PR

- [ ] **Paso 1: `README.md`**: diferencia entre margen contable (AVCO) y margen de
reposición; el costo se fija al sincronizar la orden; fallback a AVCO; **las órdenes
anteriores a la instalación quedan sin margen de reposición a propósito**; dónde verlo
(orden POS, análisis de POS como medida "Margen de reposición"); que en **ventas** el
margen de reposición lo da `product_replenishment_cost_sale_margin` de Adhoc.

- [ ] **Paso 2: instalación sobre una base con datos** (anotar en el PR): instalar en una
copia con órdenes existentes; verificar que la instalación es rápida y que las órdenes
históricas quedan con margen de reposición 0 (lo garantiza el `pre_init_hook`).

- [ ] **Paso 3: commit, push y PR contra `19.0`.**

```bash
git add alpardata_pos_replacement_margin
git commit -m "docs(pos_replacement_margin): README"
git push -u origin feat/pos-replacement-margin
```
