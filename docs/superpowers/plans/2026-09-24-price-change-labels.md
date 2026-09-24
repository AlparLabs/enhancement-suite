# Margen Erosionado y Etiquetas Pendientes — Plan de implementación

> **Para agentes:** implementar tarea por tarea, en orden. Cada paso usa checkbox (`- [ ]`).
> Si usás superpowers: REQUIRED SUB-SKILL `superpowers:subagent-driven-development` o
> `superpowers:executing-plans`.

**Goal:** Crear `alpardata_price_change_labels`: detectar productos con recargo sobre
reposición por debajo del objetivo y mantener una cola de etiquetas de góndola pendientes
de reimprimir cuando el precio cambió.

**Architecture:** Un modelo `product.price.watch` (una fila por producto y empresa)
guarda la foto del precio de góndola, la reposición y el último precio impreso. Un
proceso de refresco (cron diario + botón) actualiza las fotos usando **la misma función
que imprime la etiqueta 3x8** (`_get_label_info`). Imprimir etiquetas 3x8 regulares
registra el precio impreso.

**Tech Stack:** Odoo 19.0.

**Spec:** `docs/superpowers/specs/2026-09-24-price-change-labels-design.md`
**Requisitos previos:** punto 1 (`alpardata_replenishment_cost`, sobre Adhoc) mergeado;
`product_label_3x8` en el repo (ya existe).
**Actualizado a Adhoc:** 2026-09-24. El costo es `replenishment_cost` de Adhoc, el recargo
objetivo es `sale_margin` (margen del precio planificado, con margen por categoría del
punto 1) y "Aplicar precio sugerido" usa la actualización de precio planificado de Adhoc.

---

## Convenciones

- **Rama:** `feat/price-change-labels` desde `19.0`.
- Strings y commits en castellano: `feat(price_change_labels): ...`.
- **Odoo 19:** `<list>`, `invisible="expr"`, `<chatter/>`, `<search>` sin
  `<group string>`, `models.Constraint` para restricciones SQL.
- Fuente de Odoo: `C:\Users\Santiago\Desktop\Odoo\odoo-19.0`.
- **Addons path:** además de `enhancement-suite`, `AlparLabs/product` rama `19.0` (Adhoc).
- **Adhoc actualiza `list_price` por SQL** (`product_planned_price`,
  `_update_prices_from_planned`): después de llamarlo hay que invalidar la caché
  (`templates.invalidate_recordset(['list_price'])`) antes de leer precios.
- **Tests:**

  ```bash
  odoo-bin -c odoo.conf -d odoo19_dev -u alpardata_price_change_labels --test-enable --test-tags /alpardata_price_change_labels --stop-after-init --log-level=test
  ```

  Sin instancia: `python -m py_compile` + parseo XML con lxml; commit con
  `[tests no ejecutados]`.

## Mapa de archivos (nuevo, bajo `alpardata_price_change_labels/`)

- `__init__.py` (incluye `post_init_hook`), `__manifest__.py`, `README.md`
- `models/__init__.py`
- `models/res_company.py`, `models/res_config_settings.py`
- `models/product_price_watch.py` — fotos, refresco, cron, impresión
- `wizard/__init__.py`, `wizard/product_label_layout.py` — registrar impresión y aviso
- `data/ir_cron.xml`
- `security/security.xml`, `security/ir.model.access.csv`
- `views/product_price_watch_views.xml`, `views/res_config_settings_views.xml`,
  `views/product_label_layout_views.xml`, `views/menus.xml`
- `tests/__init__.py`, `tests/common.py`, `tests/test_markup.py`,
  `tests/test_label_queue.py`, `tests/test_planned_price.py`

---

### Tarea 1: Esqueleto, empresa y ajustes

**Files:** Create `__init__.py`, `__manifest__.py`, `models/__init__.py`,
`models/res_company.py`, `models/res_config_settings.py`, `wizard/__init__.py`,
`tests/__init__.py`, `tests/common.py`.

- [ ] **Paso 1: `__init__.py`**

```python
from . import models
from . import wizard


def post_init_hook(env):
    """Al instalar, toma la foto de precios y la marca como impresa para que no
    queden todos los productos como etiqueta pendiente."""
    watch = env['product.price.watch'].sudo()
    for company in env['res.company'].search([]):
        watches = watch._refresh_company(company)
        for rec in watches:
            rec.label_printed_price = rec.shelf_price
```

- [ ] **Paso 2: `__manifest__.py`**

```python
{
    'name': 'AlparData - Margen Erosionado y Etiquetas Pendientes',
    'version': '19.0.1.0.0',
    'summary': 'Alerta de recargo bajo objetivo sobre costo de reposición y cola de etiquetas de góndola a reimprimir',
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Inventory/Purchase',
    'license': 'AGPL-3',
    'depends': ['alpardata_replenishment_cost', 'product_label_3x8'],
    'data': [],  # la tarea 4 agrega seguridad, cron y vistas
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

> `post_init_hook` usa `product.price.watch`, que se crea en la tarea 2. Hasta entonces
> el módulo no se instala limpio: está bien, se prueba a partir de la tarea 2.

- [ ] **Paso 3: `models/__init__.py`**

```python
from . import res_company
from . import res_config_settings
# from . import product_price_watch
```

`wizard/__init__.py`:

```python
# from . import product_label_layout
```

`tests/__init__.py`:

```python
# from . import test_markup
# from . import test_label_queue
# from . import test_planned_price
```

- [ ] **Paso 4: `models/res_company.py`**

```python
from __future__ import annotations

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    shelf_pricelist_id = fields.Many2one(
        'product.pricelist', string='Lista de góndola',
        help='Lista con la que se imprimen las etiquetas de góndola. Vacía: precio de venta.',
    )
    markup_tolerance_pct = fields.Float(
        string='Tolerancia de recargo (puntos)', default=2.0,
        help='Se alerta cuando el recargo actual queda por debajo del objetivo menos esta tolerancia.',
    )
```

- [ ] **Paso 5: `models/res_config_settings.py`**

```python
from __future__ import annotations

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shelf_pricelist_id = fields.Many2one(
        related='company_id.shelf_pricelist_id', readonly=False,
    )
    markup_tolerance_pct = fields.Float(
        related='company_id.markup_tolerance_pct', readonly=False,
    )
```

- [ ] **Paso 6: `tests/common.py`**

```python
from __future__ import annotations

from odoo.tests.common import TransactionCase


class PriceWatchCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor Góndola'})
        # margen por categoría de alpardata_replenishment_cost (sale_margin de Adhoc)
        cls.categ = cls.env['product.category'].create({
            'name': 'Almacén Test', 'sale_margin': 40.0,
        })
        cls.tax = cls.env['account.tax'].create({
            'name': 'IVA 21 incluido test',
            'amount': 21.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'company_id': cls.company.id,
        })
        cls.template = cls.env['product.template'].create({
            'name': 'Fideos 500g',
            'categ_id': cls.categ.id,
            'list_price': 1694.0,  # 1400 sin IVA
            'taxes_id': [(6, 0, cls.tax.ids)],
            'sale_ok': True,
            'replenishment_cost_type': 'supplier_price',
        })
        cls.seller = cls.env['product.supplierinfo'].create({
            'partner_id': cls.partner.id,
            'product_tmpl_id': cls.template.id,
            'price': 1000.0,
        })
        cls.watch_model = cls.env['product.price.watch']

    def _watch(self, template=None):
        return self.watch_model._refresh(template or self.template, self.company)
```

> El campo que marca un impuesto como "precio incluido" en 19 es `price_include_override`
> (`'tax_included'`). Verificar en `odoo-19.0/addons/account/models/account_tax.py`; si
> es otro, ajustar. El resultado esperado del test depende de que `_get_label_info`
> calcule el neto dividiendo por 1,21.

- [ ] **Paso 7:** no correr todavía (falta el modelo del hook). Commit:

```bash
git add alpardata_price_change_labels
git commit -m "feat(price_change_labels): esqueleto y lista de góndola"
```

---

### Tarea 2: Modelo `product.price.watch` y refresco

**Files:** Create `models/product_price_watch.py`, `tests/test_markup.py`.

- [ ] **Paso 1: test que falla** — `tests/test_markup.py` (descomentarlo en
`tests/__init__.py`):

```python
from __future__ import annotations

from odoo.tests import tagged

from .common import PriceWatchCommon


@tagged('post_install', '-at_install')
class TestPriceWatchRefresh(PriceWatchCommon):

    def test_refresh_values(self):
        watch = self._watch()
        self.assertEqual(len(watch), 1)
        self.assertAlmostEqual(watch.shelf_price, 1694.0, places=2)
        self.assertAlmostEqual(watch.shelf_price_untaxed, 1400.0, places=2)
        self.assertAlmostEqual(watch.replacement_cost, 1000.0, places=2)
        self.assertAlmostEqual(watch.markup_pct, 40.0, places=2)
        self.assertEqual(watch.markup_alert, 'ok')

    def test_refresh_is_idempotent(self):
        first = self._watch()
        second = self._watch()
        self.assertEqual(first, second)

    def test_markup_below_target(self):
        self.seller.price = 1100.0  # recargo 27,27 %
        watch = self._watch()
        self.assertEqual(watch.markup_alert, 'below')

    def test_tolerance(self):
        self.seller.price = 1010.0  # recargo 38,6 %: dentro de 2 puntos
        self.assertEqual(self._watch().markup_alert, 'ok')

    def test_no_cost(self):
        template = self.env['product.template'].create({'name': 'Sin proveedor', 'sale_ok': True})
        self.assertEqual(self._watch(template).markup_alert, 'no_cost')

    def test_shelf_pricelist(self):
        pricelist = self.env['product.pricelist'].create({
            'name': 'Góndola test',
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'fixed',
                'fixed_price': 2000.0,
            })],
        })
        self.company.shelf_pricelist_id = pricelist
        self.assertAlmostEqual(self._watch().shelf_price, 2000.0, places=2)

    def test_per_company(self):
        other = self.env['res.company'].create({'name': 'Sucursal Góndola'})
        mine = self._watch()
        theirs = self.watch_model._refresh(self.template, other)
        self.assertNotEqual(mine, theirs)
        self.assertEqual(theirs.company_id, other)
```

- [ ] **Paso 2: `models/product_price_watch.py`**

```python
from __future__ import annotations

import logging
import threading

from odoo import _, api, fields, models
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

LABEL_REPORT = 'report.product_label_3x8.report_producttemplatelabel3x8'
BATCH_SIZE = 1000


class ProductPriceWatch(models.Model):
    _name = 'product.price.watch'
    _description = 'Control de precio de góndola'
    _order = 'label_pending desc, product_tmpl_id'
    _rec_name = 'product_tmpl_id'
    _check_company_auto = True

    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    categ_id = fields.Many2one(related='product_tmpl_id.categ_id', store=True, string='Categoría')
    shelf_price = fields.Monetary(string='Precio de góndola')
    shelf_price_untaxed = fields.Monetary(string='Precio sin impuestos')
    replacement_cost = fields.Monetary(string='Costo de reposición')
    target_markup_pct = fields.Float(
        related='product_tmpl_id.sale_margin', string='Recargo objetivo (%)',
        help='Margen del precio planificado (Adhoc), heredado de la categoría.',
    )
    markup_pct = fields.Float(
        string='Recargo actual (%)', compute='_compute_markup', store=True, digits=(16, 2),
    )
    markup_alert = fields.Selection(
        [('ok', 'OK'), ('below', 'Bajo objetivo'), ('no_cost', 'Sin costo')],
        string='Margen', compute='_compute_markup', store=True, index=True,
    )
    label_printed_price = fields.Monetary(string='Precio impreso')
    label_printed_date = fields.Datetime(string='Impresa el')
    label_variation_pct = fields.Float(
        string='Variación (%)', compute='_compute_label_pending', store=True, digits=(16, 2),
    )
    label_pending = fields.Boolean(
        string='Etiqueta pendiente', compute='_compute_label_pending', store=True, index=True,
    )
    refreshed_at = fields.Datetime(string='Actualizado')

    _product_company_uniq = models.Constraint(
        'UNIQUE(product_tmpl_id, company_id)',
        'Ya existe un control de precio para ese producto y empresa.',
    )

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('shelf_price_untaxed', 'replacement_cost',
                 'target_markup_pct', 'company_id.markup_tolerance_pct')
    def _compute_markup(self) -> None:
        for rec in self:
            if not rec.replacement_cost:
                rec.markup_pct = 0.0
                rec.markup_alert = 'no_cost'
                continue
            rec.markup_pct = (rec.shelf_price_untaxed / rec.replacement_cost - 1) * 100
            floor = rec.target_markup_pct - rec.company_id.markup_tolerance_pct
            rec.markup_alert = 'below' if rec.markup_pct < floor else 'ok'

    @api.depends('shelf_price', 'label_printed_price')
    def _compute_label_pending(self) -> None:
        for rec in self:
            rec.label_pending = float_compare(
                rec.shelf_price, rec.label_printed_price, precision_digits=2,
            ) != 0
            rec.label_variation_pct = (
                (rec.shelf_price / rec.label_printed_price - 1) * 100
                if rec.label_printed_price else 0.0
            )

    # ── Refresco ──────────────────────────────────────────────────────────────
    @api.model
    def _label_price(self, template, company, pricelist):
        """(precio final, precio sin impuestos) tal como los imprime la etiqueta 3x8."""
        report = self.env[LABEL_REPORT].with_company(company)
        info = report._get_label_info(template.with_company(company), pricelist=pricelist or None)
        return info['price_final'], info['price_net']

    @api.model
    def _refresh(self, templates, company):
        """Crea o actualiza las filas de `templates` para `company`. Devuelve las filas."""
        self = self.sudo()
        existing = self.search([
            ('product_tmpl_id', 'in', templates.ids), ('company_id', '=', company.id),
        ])
        by_template = {rec.product_tmpl_id.id: rec for rec in existing}
        pricelist = company.shelf_pricelist_id
        now = fields.Datetime.now()
        to_create = []
        for template in templates:
            price, untaxed = self._label_price(template, company, pricelist)
            vals = {
                'shelf_price': price,
                'shelf_price_untaxed': untaxed,
                'replacement_cost': template.with_company(company).replenishment_cost,
                'refreshed_at': now,
            }
            rec = by_template.get(template.id)
            if rec:
                rec.write(vals)
            else:
                to_create.append({
                    **vals,
                    'product_tmpl_id': template.id,
                    'company_id': company.id,
                    'label_printed_price': 0.0,
                })
        created = self.create(to_create) if to_create else self.browse()
        return existing | created

    @api.model
    def _templates_for_company(self, company):
        return self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('company_id', 'in', [company.id, False]),
        ])

    @api.model
    def _refresh_company(self, company):
        templates = self._templates_for_company(company)
        result = self.browse()
        testing = getattr(threading.current_thread(), 'testing', False)
        for start in range(0, len(templates), BATCH_SIZE):
            result |= self._refresh(templates[start:start + BATCH_SIZE], company)
            if not testing:
                self.env.cr.commit()
        return result

    @api.model
    def _cron_refresh(self) -> None:
        for company in self.env['res.company'].search([]):
            _logger.info('Control de precios de góndola: empresa %s', company.name)
            self._refresh_company(company)

    def action_refresh(self) -> None:
        for company in self.company_id:
            recs = self.filtered(lambda r: r.company_id == company)
            self._refresh(recs.product_tmpl_id, company)

    # ── Impresión ─────────────────────────────────────────────────────────────
    @api.model
    def _mark_printed(self, templates, company, pricelist):
        """Registra el precio impreso con `pricelist` (la del wizard)."""
        watches = self._refresh(templates, company)
        now = fields.Datetime.now()
        for rec in watches:
            price, _untaxed = self._label_price(rec.product_tmpl_id, company, pricelist)
            rec.write({'label_printed_price': price, 'label_printed_date': now})
        return watches

    def action_print_labels(self) -> dict:
        company = self.company_id[:1] or self.env.company
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imprimir etiquetas'),
            'res_model': 'product.label.layout',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_product_tmpl_ids': self.product_tmpl_id.ids,
                'default_print_format': '3x8xprice',
                'default_pricelist_id': company.shelf_pricelist_id.id,
            },
        }
```

> `_get_label_info` está en `product_label_3x8/report/product_label_report.py`; con
> `is_promo=False` devuelve el precio regular. Si su firma cambió, adaptar `_label_price`
> y nada más.

- [ ] **Paso 3: descomentar** `product_price_watch` en `models/__init__.py`. Agregar ACL
mínima para que los tests carguen — `security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_price_watch_user,product.price.watch.user,model_product_price_watch,base.group_user,1,0,0,0
access_price_watch_manager,product.price.watch.manager,model_product_price_watch,purchase.group_purchase_manager,1,1,1,1
```

y en el manifest `'data': ['security/ir.model.access.csv'],`.

- [ ] **Paso 4: correr tests** → `TestTargetMarkup` y `TestPriceWatchRefresh` pasan.

- [ ] **Paso 5: commit**

```bash
git add alpardata_price_change_labels
git commit -m "feat(price_change_labels): control de precio de góndola y recargo sobre reposición"
```

---

### Tarea 3: Cola de etiquetas (impresión y hook de instalación)

**Files:** Create `wizard/product_label_layout.py`, `tests/test_label_queue.py`.

- [ ] **Paso 1: test que falla** — `tests/test_label_queue.py`

```python
from __future__ import annotations

from odoo.tests import tagged

from odoo.addons.alpardata_price_change_labels import post_init_hook

from .common import PriceWatchCommon


@tagged('post_install', '-at_install')
class TestLabelQueue(PriceWatchCommon):

    def _print(self, fmt='3x8xprice', pricelist=None):
        wizard = self.env['product.label.layout'].create({
            'product_tmpl_ids': [(6, 0, self.template.ids)],
            'print_format': fmt,
            'pricelist_id': pricelist.id if pricelist else False,
        })
        wizard.process()

    def test_new_product_is_pending(self):
        self.assertTrue(self._watch().label_pending)

    def test_print_clears_pending(self):
        self._watch()
        self._print()
        watch = self._watch()
        self.assertFalse(watch.label_pending)
        self.assertAlmostEqual(watch.label_printed_price, 1694.0, places=2)
        self.assertTrue(watch.label_printed_date)

    def test_price_change_makes_pending(self):
        self._print()
        self.template.list_price = 1800.0
        watch = self._watch()
        self.assertTrue(watch.label_pending)
        self.assertAlmostEqual(watch.label_variation_pct, (1800 / 1694 - 1) * 100, places=2)

    def test_promo_does_not_clear(self):
        self._watch()
        self._print(fmt='3x8xpromo')
        self.assertTrue(self._watch().label_pending)

    def test_other_pricelist_keeps_pending(self):
        other = self.env['product.pricelist'].create({
            'name': 'Mayorista test',
            'item_ids': [(0, 0, {
                'applied_on': '3_global', 'compute_price': 'fixed', 'fixed_price': 1500.0,
            })],
        })
        self._print(pricelist=other)
        self.assertTrue(self._watch().label_pending)

    def test_post_init_hook_leaves_nothing_pending(self):
        post_init_hook(self.env)
        pending = self.watch_model.search([
            ('company_id', '=', self.company.id), ('label_pending', '=', True),
        ])
        self.assertFalse(pending)

    def test_cost_change_with_planned_price(self):
        """Precio por margen: sube el costo, se actualiza el precio planificado →
        etiqueta pendiente."""
        self.template.list_price_type = 'by_margin'  # 1000 × 1,40 × 1,21 = 1694
        self._print()
        self.assertFalse(self._watch().label_pending)
        self.seller.price = 1100.0
        self.template._update_prices_from_planned()
        self.template.invalidate_recordset(['list_price'])
        self.assertTrue(self._watch().label_pending)
```

- [ ] **Paso 2: `wizard/product_label_layout.py`**

```python
from __future__ import annotations

from odoo import api, fields, models


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    shelf_pricelist_warning = fields.Char(compute='_compute_shelf_pricelist_warning')

    @api.depends('pricelist_id', 'print_format')
    def _compute_shelf_pricelist_warning(self) -> None:
        shelf = self.env.company.shelf_pricelist_id
        for wizard in self:
            if wizard.print_format == '3x8xprice' and wizard.pricelist_id != shelf:
                wizard.shelf_pricelist_warning = (
                    f'La lista elegida no es la lista de góndola '
                    f'({shelf.display_name or "precio de venta"}): los productos '
                    f'seguirán como etiqueta pendiente.'
                )
            else:
                wizard.shelf_pricelist_warning = False

    def process(self):
        action = super().process()
        if self.print_format == '3x8xprice':
            templates = self.product_tmpl_ids or self.product_ids.product_tmpl_id
            self.env['product.price.watch'].sudo()._mark_printed(
                templates, self.env.company, self.pricelist_id,
            )
        return action
```

- [ ] **Paso 3: descomentar** `product_label_layout` en `wizard/__init__.py` y
`test_label_queue` en `tests/__init__.py`.

- [ ] **Paso 4: correr tests** → pasan. Si `process()` falla en el test por el renderizado
del PDF (wkhtmltopdf ausente), no importa: `process()` sólo devuelve la acción del
reporte, no renderiza. Si igual renderizara, parchear en el test
`self.patch(type(self.env['ir.actions.report']), 'report_action', lambda *a, **k: {})`.

- [ ] **Paso 5: commit**

```bash
git add alpardata_price_change_labels
git commit -m "feat(price_change_labels): cola de etiquetas pendientes al imprimir 3x8"
```

---

### Tarea 4: Seguridad, cron, vistas y menús

**Files:** Create `security/security.xml`, `data/ir_cron.xml`, las vistas.

- [ ] **Paso 1: `security/security.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="rule_price_watch_company" model="ir.rule">
        <field name="name">Control de precio de góndola: multi-empresa</field>
        <field name="model_id" ref="model_product_price_watch"/>
        <field name="global" eval="True"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
    </record>
</odoo>
```

- [ ] **Paso 2: `data/ir_cron.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="ir_cron_price_watch_refresh" model="ir.cron">
        <field name="name">Góndola: actualizar precios y etiquetas pendientes</field>
        <field name="model_id" ref="model_product_price_watch"/>
        <field name="state">code</field>
        <field name="code">model._cron_refresh()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="active" eval="True"/>
    </record>
</odoo>
```

- [ ] **Paso 3: `views/product_price_watch_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="product_price_watch_view_list_labels" model="ir.ui.view">
        <field name="name">product.price.watch.list.labels</field>
        <field name="model">product.price.watch</field>
        <field name="arch" type="xml">
            <list create="0" edit="0" delete="0">
                <header>
                    <button name="action_print_labels" type="object" string="Imprimir etiquetas"
                            class="btn-primary"/>
                    <button name="action_refresh" type="object" string="Actualizar"/>
                </header>
                <field name="product_tmpl_id"/>
                <field name="categ_id" optional="show"/>
                <field name="currency_id" column_invisible="1"/>
                <field name="label_printed_price"/>
                <field name="shelf_price"/>
                <field name="label_variation_pct"
                       decoration-danger="label_variation_pct &gt; 0"
                       decoration-success="label_variation_pct &lt; 0"/>
                <field name="label_printed_date" optional="show"/>
                <field name="refreshed_at" optional="hide"/>
                <field name="company_id" groups="base.group_multi_company" optional="hide"/>
            </list>
        </field>
    </record>

    <record id="product_price_watch_view_list_markup" model="ir.ui.view">
        <field name="name">product.price.watch.list.markup</field>
        <field name="model">product.price.watch</field>
        <field name="priority">20</field>
        <field name="arch" type="xml">
            <list create="0" edit="0" delete="0">
                <header>
                    <button name="action_refresh" type="object" string="Actualizar"/>
                </header>
                <field name="product_tmpl_id"/>
                <field name="categ_id" optional="show"/>
                <field name="currency_id" column_invisible="1"/>
                <field name="replacement_cost"/>
                <field name="shelf_price_untaxed"/>
                <field name="markup_pct"/>
                <field name="target_markup_pct"/>
                <field name="markup_alert" widget="badge"
                       decoration-success="markup_alert == 'ok'"
                       decoration-danger="markup_alert == 'below'"
                       decoration-muted="markup_alert == 'no_cost'"/>
                <field name="company_id" groups="base.group_multi_company" optional="hide"/>
            </list>
        </field>
    </record>

    <record id="product_price_watch_view_search" model="ir.ui.view">
        <field name="name">product.price.watch.search</field>
        <field name="model">product.price.watch</field>
        <field name="arch" type="xml">
            <search>
                <field name="product_tmpl_id"/>
                <field name="categ_id"/>
                <filter name="filter_label_pending" string="Etiqueta pendiente"
                        domain="[('label_pending', '=', True)]"/>
                <filter name="filter_below" string="Margen bajo objetivo"
                        domain="[('markup_alert', '=', 'below')]"/>
                <group>
                    <filter name="group_categ" string="Categoría" context="{'group_by': 'categ_id'}"/>
                </group>
            </search>
        </field>
    </record>

    <record id="action_price_watch_labels" model="ir.actions.act_window">
        <field name="name">Etiquetas pendientes</field>
        <field name="res_model">product.price.watch</field>
        <field name="view_mode">list</field>
        <field name="view_id" ref="product_price_watch_view_list_labels"/>
        <field name="context">{'search_default_filter_label_pending': 1}</field>
    </record>

    <record id="action_price_watch_markup" model="ir.actions.act_window">
        <field name="name">Margen erosionado</field>
        <field name="res_model">product.price.watch</field>
        <field name="view_mode">list</field>
        <field name="view_id" ref="product_price_watch_view_list_markup"/>
        <field name="context">{'search_default_filter_below': 1}</field>
    </record>
</odoo>
```

- [ ] **Paso 4: `views/res_config_settings_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form_shelf" model="ir.ui.view">
        <field name="name">res.config.settings.form.shelf</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="purchase.res_config_settings_view_form_purchase"/>
        <field name="arch" type="xml">
            <xpath expr="//app[@name='purchase']" position="inside">
                <block title="Góndola" name="shelf_settings">
                <setting string="Góndola"
                         help="Lista con la que se imprimen las etiquetas de góndola y tolerancia antes de alertar margen bajo.">
                    <div class="content-group">
                        <div class="row">
                            <label for="shelf_pricelist_id" class="col-lg-5 o_light_label"/>
                            <field name="shelf_pricelist_id" class="col-lg-6"/>
                        </div>
                        <div class="row mt4">
                            <label for="markup_tolerance_pct" class="col-lg-5 o_light_label"/>
                            <field name="markup_tolerance_pct" class="col-lg-2"/>
                        </div>
                    </div>
                </setting>
                </block>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Paso 5: `views/product_label_layout_views.xml`** (aviso en el wizard)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="product_label_layout_form_shelf_warning" model="ir.ui.view">
        <field name="name">product.label.layout.form.shelf.warning</field>
        <field name="model">product.label.layout</field>
        <field name="inherit_id" ref="product.product_label_layout_form"/>
        <field name="arch" type="xml">
            <xpath expr="//form/*[1]" position="before">
                <div class="alert alert-warning" role="alert" invisible="not shelf_pricelist_warning">
                    <field name="shelf_pricelist_warning" nolabel="1"/>
                </div>
            </xpath>
        </field>
    </record>
</odoo>
```

> Verificar el id de la vista del wizard en `odoo-19.0/addons/product/wizard/product_label_layout_views.xml`.

- [ ] **Paso 6: `views/menus.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_price_watch_labels"
              name="Etiquetas pendientes"
              parent="stock.menu_stock_inventory_control"
              action="action_price_watch_labels"
              sequence="90"/>
    <menuitem id="menu_price_watch_markup"
              name="Margen erosionado"
              parent="purchase.menu_purchase_products"
              action="action_price_watch_markup"
              sequence="45"/>
</odoo>
```

- [ ] **Paso 7: manifest `data`** completo:

```python
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/product_price_watch_views.xml',
        'views/res_config_settings_views.xml',
        'views/product_label_layout_views.xml',
        'views/menus.xml',
    ],
```

- [ ] **Paso 8: instalar en base limpia** y correr todos los tests:

```bash
odoo-bin -c odoo.conf -d odoo19_labels_test -i alpardata_price_change_labels --test-enable --test-tags /alpardata_price_change_labels --stop-after-init --log-level=test
```
Esperado: 0 fallas; el `post_init_hook` no rompe.

- [ ] **Paso 9: prueba manual** (anotar en el PR): configurar lista de góndola, cambiar el
precio de un producto, "Actualizar" → aparece en Etiquetas pendientes; "Imprimir
etiquetas" → sale el PDF 3x8 y la fila desaparece.

- [ ] **Paso 10: commit**

```bash
git add alpardata_price_change_labels
git commit -m "feat(price_change_labels): seguridad, cron, vistas y menús"
```

---

### Tarea 5: Actualizar precio planificado desde "Margen erosionado"

**Files:** Modify `models/product_price_watch.py`, `views/product_price_watch_views.xml`,
`tests/__init__.py`; Create `tests/test_planned_price.py`.

El cálculo del precio sugerido (reposición × (1 + margen) + recargo, con impuestos
incluidos) es el **precio planificado de Adhoc** (`product_planned_price`). Este módulo
sólo agrega un botón en "Margen erosionado" que lo aplica a las filas seleccionadas y
refresca la cola de etiquetas.

- [ ] **Paso 1: test que falla** — `tests/test_planned_price.py` (y
`from . import test_planned_price` en `tests/__init__.py`)

```python
from __future__ import annotations

from odoo.tests import tagged

from .common import PriceWatchCommon


@tagged('post_install', '-at_install')
class TestPlannedPrice(PriceWatchCommon):

    def test_apply_updates_list_price_and_queue(self):
        self.template.list_price_type = 'by_margin'
        self.seller.price = 1100.0  # 1100 × 1,40 × 1,21 = 1863,40
        watch = self._watch()
        watch.action_apply_planned_price()
        self.assertAlmostEqual(self.template.list_price, 1863.4, places=2)
        refreshed = self._watch()
        self.assertAlmostEqual(refreshed.shelf_price, 1863.4, places=2)
        self.assertEqual(refreshed.markup_alert, 'ok')

    def test_manual_price_products_reported(self):
        self.seller.price = 1100.0  # list_price_type 'manual' (default de Adhoc)
        result = self._watch().action_apply_planned_price()
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(self.template.list_price, 1694.0)
```

> Si el tipo de precio por defecto de Adhoc no es `manual` en tu versión, crear el
> producto del test con `list_price_type='manual'` explícito.

- [ ] **Paso 2: correr** → falla.

- [ ] **Paso 3: agregar a `models/product_price_watch.py`**

```python
    def action_apply_planned_price(self):
        """Pasa el precio planificado de Adhoc al precio de venta de los productos
        "por margen" seleccionados y refresca sus filas. Los productos con precio
        manual se informan: su precio se cambia a mano."""
        templates = self.product_tmpl_id
        by_margin = templates.filtered(lambda t: t.list_price_type == 'by_margin')
        by_margin._update_prices_from_planned()
        # Adhoc escribe list_price por SQL: la caché del ORM queda vieja.
        by_margin.invalidate_recordset(['list_price'])
        for company in self.company_id:
            rows = self.filtered(lambda r: r.company_id == company)
            self._refresh(rows.product_tmpl_id, company)
        manual = templates - by_margin
        if manual:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Precio planificado'),
                    'message': _(
                        '%s producto(s) tienen precio manual: no se actualizaron. '
                        'Para calcularlos por margen, cambiá su tipo de precio planificado.',
                        len(manual),
                    ),
                    'type': 'warning',
                    'sticky': True,
                },
            }
        return True
```

- [ ] **Paso 4: vista** — en `views/product_price_watch_views.xml`, dentro del `<header>`
de `product_price_watch_view_list_markup`, antes del botón "Actualizar":

```xml
                    <button name="action_apply_planned_price" type="object"
                            string="Actualizar precio planificado" class="btn-primary"
                            groups="purchase.group_purchase_manager"
                            confirm="Se pasa el precio planificado al precio de venta de los productos seleccionados que tienen precio por margen. ¿Continuar?"/>
```

- [ ] **Paso 5: correr** → `TestPlannedPrice` pasa.

- [ ] **Paso 6: commit**

```bash
git add alpardata_price_change_labels
git commit -m "feat(price_change_labels): actualizar precio planificado desde margen erosionado"
```

---

### Tarea 6: README y PR

- [ ] **Paso 1: `README.md`**: qué resuelve, cómo configurar lista de góndola y margen
(el recargo objetivo es el margen por categoría del punto 1), cuándo se actualiza (cron diario + botón), qué vacía la cola (sólo 3x8 regular
con la lista de góndola), y la sección **Redondeo comercial** del spec (terminar en 99:
redondeo 100 y recargo −1; múltiplos de 50: redondeo 50) usando las reglas de lista
estándar. Sumar "Actualizar precio planificado": usa el precio planificado de Adhoc
(sólo productos "por margen"), y que `list_price` es el mismo para todas las empresas.
- [ ] **Paso 2: commit, push y PR contra `19.0`.**

```bash
git add alpardata_price_change_labels/README.md
git commit -m "docs(price_change_labels): README"
git push -u origin feat/price-change-labels
```
