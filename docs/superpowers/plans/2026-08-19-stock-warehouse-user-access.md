# Stock Warehouse User Access — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el módulo `stock_warehouse_user_access`, que limita la visibilidad de transferencias y órdenes de compra al almacén asignado a cada usuario, sin impedir las transferencias entre almacenes.

**Architecture:** Dos campos nuevos en `res.users` (almacenes permitidos + almacén por defecto) alimentan cuatro `ir.rule`: un par restrictivo/permisivo sobre `stock.picking` y otro sobre `purchase.order`. La restricción de los desplegables NO usa reglas de registro sobre `stock.picking.type` —eso rompería las rutas de reabastecimiento— sino un override de `_search` que solo actúa cuando el contexto trae `restrict_to_user_warehouses`. Los valores por defecto se resuelven en `default_get`, no sobreescribiendo `_default_picking_type`.

**Tech Stack:** Odoo 18.0, Python, XML (vistas + seguridad), `TransactionCase`.

**Spec:** `docs/superpowers/specs/2026-08-19-stock-warehouse-user-access-design.md`

---

## Hechos del código base que este plan da por verificados

Todos comprobados en `C:\Program Files\Odoo 18.0.20260307\server\odoo`:

- `stock.location.warehouse_id` es `store=True` (`addons/stock/models/stock_location.py:92`) → usable en `ir.rule`.
- `purchase.order.picking_type_id` se define en `purchase_stock`, no en `purchase` (`addons/purchase_stock/models/purchase_order.py:23`).
- `Environment.user` devuelve el registro **sudoed** (`api.py:687-692`) → `user.warehouse_access_ids` se lee sin problemas dentro del evaluador de `ir.rule`.
- `BaseModel._search(self, domain, offset=0, limit=None, order=None) -> Query` (`models.py:5798`).
- `post_init_hook` se invoca con un único argumento `env` (`modules/loading.py:244-246`).
- `odoo.osv.expression.AND` existe (`osv/expression.py:303`).
- La vista del formulario de albarán es `stock.view_picking_form`, y su campo `picking_type_id` está en la línea 212 de `addons/stock/views/stock_picking_views.xml`.
- La vista de compras que trae `picking_type_id` es `purchase_stock.purchase_order_view_form_inherit` (línea 76), con `groups="stock.group_stock_multi_locations"`.
- El panel "Resumen" de Inventario es la acción `stock.stock_picking_type_action` (kanban). `stock.action_picking_type_list` es otra cosa: la lista de configuración de Tipos de Operación.
- `product.product.is_storable` es el booleano de almacenable en 18 (`addons/stock/models/product.py:704`); `type` ya no tiene el valor `'product'`.
- `stock.picking.type` requiere `name`, `sequence_code`, `code` y `company_id`; las ubicaciones por defecto son `precompute` y se autocompletan.

### Por qué el grupo va en categoría propia

`res.groups.get_groups_by_application()` (`addons/base/models/res_users.py:1835-1850`) decide cómo se dibuja cada categoría en el formulario de usuario: si el orden de implicación entre sus grupos es total, la categoría se renderiza como **desplegable**; si no, degrada a **checkboxes** bajo "Other".

`base.module_category_inventory_inventory` contiene `group_stock_user` → `group_stock_manager` (orden total → desplegable). Si le agregamos un tercer grupo sin relación de implicación, el orden deja de ser total y el desplegable Usuario/Administrador de Inventario se rompe.

Por eso el módulo define su **propia** `ir.module.category`. Con un solo grupo dentro, el orden es total y se renderiza como un desplegable propio de dos opciones (vacío / "Ver todos los almacenes"). Tampoco sirve `base.module_category_hidden`: las categorías ocultas quedan detrás de `base.group_no_one` (`res_users.py:1721-1722`), o sea solo visibles en modo desarrollador.

---

## File Structure

```
stock_warehouse_user_access/
├── __init__.py                          # import models + post_init_hook
├── __manifest__.py                      # depends ['stock', 'purchase_stock']
├── hooks.py                             # post_init_hook: exime a gerentes existentes
├── models/
│   ├── __init__.py
│   ├── res_users.py                     # warehouse_access_ids, default_warehouse_id, constraint
│   ├── stock_picking_type.py            # _search filtrado por contexto
│   ├── stock_picking.py                 # default_get de picking_type_id
│   └── purchase_order.py                # default_get de picking_type_id
├── security/
│   ├── warehouse_access_groups.xml      # ir.module.category + group_warehouse_access_all
│   └── warehouse_access_rules.xml       # 4 ir.rule
├── views/
│   ├── res_users_views.xml              # campos en la pestaña de permisos
│   ├── stock_picking_views.xml          # contexto en el form + en la acción Resumen
│   └── purchase_order_views.xml         # contexto en "Entregar a"
└── tests/
    ├── __init__.py
    └── test_warehouse_access.py
```

Responsabilidades:
- `res_users.py`: solo los dos campos y su constraint. Sin lógica de negocio.
- `stock_picking_type.py`: única fuente del dominio de almacenes visibles (`_get_user_warehouse_domain`), consumida por el `_search`.
- `stock_picking.py` / `purchase_order.py`: solo el valor por defecto. Un archivo por modelo.
- Seguridad partida en dos: grupos y reglas cambian por motivos distintos.

---

## Task 1: Scaffolding del módulo

**Files:**
- Create: `stock_warehouse_user_access/__init__.py`
- Create: `stock_warehouse_user_access/__manifest__.py`
- Create: `stock_warehouse_user_access/models/__init__.py`
- Create: `stock_warehouse_user_access/tests/__init__.py`

- [ ] **Step 1: Crear el manifiesto**

`stock_warehouse_user_access/__manifest__.py`:

```python
{
    'name': 'Acceso por Almacén',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Limita la visibilidad de transferencias y órdenes de compra al almacén asignado a cada usuario.',
    'author': 'AlparData',
    'depends': ['stock', 'purchase_stock'],
    'data': [
        'security/warehouse_access_groups.xml',
        'security/warehouse_access_rules.xml',
        'views/res_users_views.xml',
        'views/stock_picking_views.xml',
        'views/purchase_order_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
```

- [ ] **Step 2: Crear los `__init__.py`**

`stock_warehouse_user_access/__init__.py`:

```python
from . import models
from .hooks import post_init_hook
```

`stock_warehouse_user_access/models/__init__.py`:

```python
from . import res_users
from . import stock_picking_type
from . import stock_picking
from . import purchase_order
```

`stock_warehouse_user_access/tests/__init__.py`:

```python
from . import test_warehouse_access
```

- [ ] **Step 3: Commit**

El módulo todavía no instala (faltan los archivos referenciados); se commitea el andamiaje para tener un punto de retorno.

```bash
git add stock_warehouse_user_access/__init__.py stock_warehouse_user_access/__manifest__.py stock_warehouse_user_access/models/__init__.py stock_warehouse_user_access/tests/__init__.py
git commit -m "feat(stock_warehouse_user_access): scaffolding del modulo"
```

---

## Task 2: Categoría y grupo de excepción

**Files:**
- Create: `stock_warehouse_user_access/security/warehouse_access_groups.xml`

- [ ] **Step 1: Crear el archivo de grupos**

`stock_warehouse_user_access/security/warehouse_access_groups.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <record id="module_category_warehouse_access" model="ir.module.category">
            <field name="name">Acceso por Almacén</field>
            <field name="description">Controla qué almacenes puede ver cada usuario en transferencias y compras.</field>
            <field name="sequence">20</field>
        </record>

        <record id="group_warehouse_access_all" model="res.groups">
            <field name="name">Ver todos los almacenes</field>
            <field name="category_id" ref="module_category_warehouse_access"/>
            <field name="comment">Exime al usuario del filtro por almacén: ve todas las transferencias y órdenes de compra de sus compañías.</field>
        </record>

    </data>
</odoo>
```

El grupo **no** lleva `implied_ids`: es ortogonal a los permisos de inventario y de compras.

- [ ] **Step 2: Instalar el módulo y verificar el grupo**

Run:
```bash
odoo -d <db> -i stock_warehouse_user_access --stop-after-init
```
Expected: instala sin error. En Ajustes → Usuarios → un usuario, aparece la sección "Acceso por Almacén" con un desplegable de dos opciones.

Nota: en este punto el manifiesto referencia archivos que todavía no existen. Antes de correr, comentá temporalmente las líneas de `data` que faltan, o ejecutá esta verificación recién al terminar la Task 4. Si elegís lo segundo, marcá este paso como hecho ahí.

- [ ] **Step 3: Commit**

```bash
git add stock_warehouse_user_access/security/warehouse_access_groups.xml
git commit -m "feat(stock_warehouse_user_access): categoria y grupo de excepcion"
```

---

## Task 3: Campos en `res.users`

**Files:**
- Create: `stock_warehouse_user_access/models/res_users.py`
- Create: `stock_warehouse_user_access/tests/test_warehouse_access.py`

- [ ] **Step 1: Escribir el test que falla**

`stock_warehouse_user_access/tests/test_warehouse_access.py`:

```python
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWarehouseAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.wh_a = cls.env['stock.warehouse'].create({
            'name': 'Sucursal A',
            'code': 'WHA',
            'company_id': cls.company.id,
        })
        cls.wh_b = cls.env['stock.warehouse'].create({
            'name': 'Sucursal B',
            'code': 'WHB',
            'company_id': cls.company.id,
        })
        cls.group_all = cls.env.ref(
            'stock_warehouse_user_access.group_warehouse_access_all'
        )
        cls.group_stock_user = cls.env.ref('stock.group_stock_user')
        cls.group_purchase_user = cls.env.ref('purchase.group_purchase_user')
        cls.user_a = cls._make_user('usuario_wh_a', cls.wh_a)
        cls.user_b = cls._make_user('usuario_wh_b', cls.wh_b)
        cls.user_none = cls._make_user('usuario_sin_wh', None)
        cls.user_all = cls._make_user('usuario_todo', None, all_access=True)
        cls.product = cls.env['product.product'].create({
            'name': 'Producto test',
            'is_storable': True,
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'Proveedor test'})

    @classmethod
    def _make_user(cls, login, warehouse, all_access=False):
        groups = cls.group_stock_user | cls.group_purchase_user
        if all_access:
            groups |= cls.group_all
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [(6, 0, groups.ids)],
            'warehouse_access_ids': [(6, 0, warehouse.ids if warehouse else [])],
            'default_warehouse_id': warehouse.id if warehouse else False,
        })

    def test_user_warehouse_fields(self):
        self.assertEqual(self.user_a.warehouse_access_ids, self.wh_a)
        self.assertEqual(self.user_a.default_warehouse_id, self.wh_a)
        self.assertFalse(self.user_none.warehouse_access_ids)

    def test_default_warehouse_must_be_allowed(self):
        with self.assertRaises(ValidationError):
            self.user_a.default_warehouse_id = self.wh_b
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: FAIL. `setUpClass` revienta con `ValueError: Invalid field 'warehouse_access_ids' on model 'res.users'`.

- [ ] **Step 3: Escribir la implementación mínima**

`stock_warehouse_user_access/models/res_users.py`:

```python
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    warehouse_access_ids = fields.Many2many(
        'stock.warehouse',
        'res_users_stock_warehouse_access_rel',
        'user_id',
        'warehouse_id',
        string='Almacenes permitidos',
        help="Almacenes cuyas transferencias y órdenes de compra puede ver el "
             "usuario. Si está vacío y el usuario no tiene el permiso 'Ver "
             "todos los almacenes', no ve ningún documento con almacén.",
    )
    default_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén por defecto',
        help="Almacén que se propone al crear una transferencia o una orden "
             "de compra. Debe estar dentro de los almacenes permitidos.",
    )

    @api.constrains('warehouse_access_ids', 'default_warehouse_id')
    def _check_default_warehouse_allowed(self):
        for user in self:
            if not user.default_warehouse_id:
                continue
            if user.default_warehouse_id not in user.warehouse_access_ids:
                raise ValidationError(_(
                    "El almacén por defecto de %(user)s debe estar dentro de "
                    "sus almacenes permitidos.",
                    user=user.name,
                ))
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: PASS los 2 tests de esta tarea.

- [ ] **Step 5: Commit**

```bash
git add stock_warehouse_user_access/models/res_users.py stock_warehouse_user_access/tests/test_warehouse_access.py
git commit -m "feat(stock_warehouse_user_access): campos de almacen en res.users"
```

---

## Task 4: Vista del formulario de usuario

**Files:**
- Create: `stock_warehouse_user_access/views/res_users_views.xml`

- [ ] **Step 1: Crear la vista heredada**

`stock_warehouse_user_access/views/res_users_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <record id="view_users_form_warehouse_access" model="ir.ui.view">
            <field name="name">res.users.form.warehouse.access</field>
            <field name="model">res.users</field>
            <field name="inherit_id" ref="base.view_users_form"/>
            <field name="arch" type="xml">
                <xpath expr="//page[@name='access_rights']/field[@name='groups_id']" position="before">
                    <group string="Acceso por Almacén" name="warehouse_access">
                        <field name="warehouse_access_ids"
                               widget="many2many_tags"
                               options="{'no_create': True}"/>
                        <field name="default_warehouse_id"
                               domain="[('id', 'in', warehouse_access_ids)]"
                               options="{'no_create': True}"/>
                    </group>
                </xpath>
            </field>
        </record>

    </data>
</odoo>
```

El `xpath` apunta al `<field name="groups_id"/>` dentro de `<page name="access_rights">` de `base.view_users_form` (confirmado en `addons/base/views/res_users_views.xml:216-222`).

- [ ] **Step 2: Actualizar y verificar en la interfaz**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --stop-after-init
```
Expected: actualiza sin error de validación de vistas. En Ajustes → Usuarios → pestaña "Permisos de acceso" aparece el grupo "Acceso por Almacén" con los dos campos, y el desplegable del almacén por defecto solo lista los almacenes ya tildados.

- [ ] **Step 3: Commit**

```bash
git add stock_warehouse_user_access/views/res_users_views.xml
git commit -m "feat(stock_warehouse_user_access): campos de almacen en el formulario de usuario"
```

---

## Task 5: Reglas de registro de `stock.picking`

**Files:**
- Create: `stock_warehouse_user_access/security/warehouse_access_rules.xml`
- Modify: `stock_warehouse_user_access/tests/test_warehouse_access.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de la clase `TestWarehouseAccess`:

```python
    def _make_picking(self, picking_type, location, location_dest):
        return self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location.id,
            'location_dest_id': location_dest.id,
        })

    def _visible_pickings(self, user):
        return self.env['stock.picking'].with_user(user).search([])

    def test_picking_of_own_warehouse_is_visible(self):
        picking = self._make_picking(
            self.wh_a.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_a.lot_stock_id,
        )
        self.assertIn(picking, self._visible_pickings(self.user_a))

    def test_picking_of_other_warehouse_is_hidden(self):
        picking = self._make_picking(
            self.wh_b.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_b.lot_stock_id,
        )
        self.assertNotIn(picking, self._visible_pickings(self.user_a))

    def test_inter_warehouse_transfer_visible_from_both_sides(self):
        picking = self._make_picking(
            self.wh_a.int_type_id,
            self.wh_a.lot_stock_id,
            self.wh_b.lot_stock_id,
        )
        self.assertIn(picking, self._visible_pickings(self.user_a))
        self.assertIn(picking, self._visible_pickings(self.user_b))

    def test_exempt_user_sees_every_picking(self):
        picking_a = self._make_picking(
            self.wh_a.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_a.lot_stock_id,
        )
        picking_b = self._make_picking(
            self.wh_b.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_b.lot_stock_id,
        )
        visible = self._visible_pickings(self.user_all)
        self.assertIn(picking_a, visible)
        self.assertIn(picking_b, visible)

    def test_user_without_warehouses_sees_no_picking(self):
        picking = self._make_picking(
            self.wh_a.in_type_id,
            self.env.ref('stock.stock_location_suppliers'),
            self.wh_a.lot_stock_id,
        )
        self.assertNotIn(picking, self._visible_pickings(self.user_none))
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: FAIL en `test_picking_of_other_warehouse_is_hidden` y `test_user_without_warehouses_sees_no_picking` — sin reglas, todo el mundo ve todo. Los otros tres pasan por accidente.

- [ ] **Step 3: Crear las reglas**

`stock_warehouse_user_access/security/warehouse_access_rules.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <record id="stock_picking_warehouse_access_rule" model="ir.rule">
            <field name="name">stock.picking: solo almacenes del usuario</field>
            <field name="model_id" ref="stock.model_stock_picking"/>
            <field name="domain_force">['|', '|', '|',
                ('picking_type_id.warehouse_id', '=', False),
                ('picking_type_id.warehouse_id', 'in', user.warehouse_access_ids.ids),
                ('location_id.warehouse_id', 'in', user.warehouse_access_ids.ids),
                ('location_dest_id.warehouse_id', 'in', user.warehouse_access_ids.ids)]</field>
            <field name="groups" eval="[(4, ref('base.group_user'))]"/>
        </record>

        <record id="stock_picking_warehouse_access_all_rule" model="ir.rule">
            <field name="name">stock.picking: ver todos los almacenes</field>
            <field name="model_id" ref="stock.model_stock_picking"/>
            <field name="domain_force">[(1, '=', 1)]</field>
            <field name="groups" eval="[(4, ref('stock_warehouse_user_access.group_warehouse_access_all'))]"/>
        </record>

    </data>
</odoo>
```

La regla restrictiva se ancla en `base.group_user`, no en `stock.group_stock_user`: un usuario sin el grupo de inventario (por ejemplo un cajero de POS) quedaría sin ninguna regla de grupo aplicable y Odoo le mostraría todo.

Las dos reglas están asociadas a grupos, así que se combinan con **OR** entre sí, y el resultado con **AND** contra la regla global multiempresa `stock.stock_picking_rule`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: PASS los 5 tests de albaranes.

- [ ] **Step 5: Commit**

```bash
git add stock_warehouse_user_access/security/warehouse_access_rules.xml stock_warehouse_user_access/tests/test_warehouse_access.py
git commit -m "feat(stock_warehouse_user_access): reglas de registro de transferencias"
```

---

## Task 6: Reglas de registro de `purchase.order`

**Files:**
- Modify: `stock_warehouse_user_access/security/warehouse_access_rules.xml`
- Modify: `stock_warehouse_user_access/tests/test_warehouse_access.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de la clase `TestWarehouseAccess`:

```python
    def _make_purchase(self, picking_type):
        return self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'picking_type_id': picking_type.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'price_unit': 100.0,
            })],
        })

    def _visible_purchases(self, user):
        return self.env['purchase.order'].with_user(user).search([])

    def _make_warehouseless_picking_type(self):
        return self.env['stock.picking.type'].create({
            'name': 'Recepción sin almacén',
            'sequence_code': 'SINWH',
            'code': 'incoming',
            'company_id': self.company.id,
            'warehouse_id': False,
            'default_location_src_id': self.env.ref('stock.stock_location_suppliers').id,
            'default_location_dest_id': self.wh_a.lot_stock_id.id,
        })

    def test_purchase_of_other_warehouse_is_hidden(self):
        order = self._make_purchase(self.wh_b.in_type_id)
        self.assertNotIn(order, self._visible_purchases(self.user_a))
        self.assertIn(order, self._visible_purchases(self.user_b))

    def test_purchase_without_warehouse_is_visible_to_everyone(self):
        order = self._make_purchase(self._make_warehouseless_picking_type())
        self.assertIn(order, self._visible_purchases(self.user_a))
        self.assertIn(order, self._visible_purchases(self.user_b))
        self.assertIn(order, self._visible_purchases(self.user_all))

    def test_exempt_user_sees_every_purchase(self):
        order_a = self._make_purchase(self.wh_a.in_type_id)
        order_b = self._make_purchase(self.wh_b.in_type_id)
        visible = self._visible_purchases(self.user_all)
        self.assertIn(order_a, visible)
        self.assertIn(order_b, visible)
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: FAIL en `test_purchase_of_other_warehouse_is_hidden` — `user_a` todavía ve la orden de WH-B.

- [ ] **Step 3: Agregar las reglas de compras**

En `stock_warehouse_user_access/security/warehouse_access_rules.xml`, antes del `</data>` de cierre:

```xml
        <record id="purchase_order_warehouse_access_rule" model="ir.rule">
            <field name="name">purchase.order: solo almacenes del usuario</field>
            <field name="model_id" ref="purchase.model_purchase_order"/>
            <field name="domain_force">['|', '|',
                ('picking_type_id', '=', False),
                ('picking_type_id.warehouse_id', '=', False),
                ('picking_type_id.warehouse_id', 'in', user.warehouse_access_ids.ids)]</field>
            <field name="groups" eval="[(4, ref('base.group_user'))]"/>
        </record>

        <record id="purchase_order_warehouse_access_all_rule" model="ir.rule">
            <field name="name">purchase.order: ver todos los almacenes</field>
            <field name="model_id" ref="purchase.model_purchase_order"/>
            <field name="domain_force">[(1, '=', 1)]</field>
            <field name="groups" eval="[(4, ref('stock_warehouse_user_access.group_warehouse_access_all'))]"/>
        </record>
```

Las dos primeras ramas del dominio restrictivo cubren servicios y dropship: sus tipos de operación tienen `warehouse_id = False` y quedan visibles para todos, según lo decidido en el spec.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: PASS los 3 tests de compras y los 5 de albaranes.

- [ ] **Step 5: Commit**

```bash
git add stock_warehouse_user_access/security/warehouse_access_rules.xml stock_warehouse_user_access/tests/test_warehouse_access.py
git commit -m "feat(stock_warehouse_user_access): reglas de registro de compras"
```

---

## Task 7: Filtrado de `stock.picking.type` por contexto

**Files:**
- Create: `stock_warehouse_user_access/models/stock_picking_type.py`
- Modify: `stock_warehouse_user_access/tests/test_warehouse_access.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de la clase `TestWarehouseAccess`:

```python
    def _searched_types(self, user, restrict):
        context = {'restrict_to_user_warehouses': True} if restrict else {}
        return self.env['stock.picking.type'].with_user(user).with_context(
            **context
        ).search([])

    def test_picking_type_search_filters_with_context(self):
        types = self._searched_types(self.user_a, restrict=True)
        self.assertIn(self.wh_a.in_type_id, types)
        self.assertNotIn(self.wh_b.in_type_id, types)

    def test_picking_type_search_unfiltered_without_context(self):
        types = self._searched_types(self.user_a, restrict=False)
        self.assertIn(self.wh_a.in_type_id, types)
        self.assertIn(self.wh_b.in_type_id, types)

    def test_picking_type_search_not_filtered_for_exempt_user(self):
        types = self._searched_types(self.user_all, restrict=True)
        self.assertIn(self.wh_a.in_type_id, types)
        self.assertIn(self.wh_b.in_type_id, types)

    def test_picking_type_search_not_filtered_without_warehouses(self):
        types = self._searched_types(self.user_none, restrict=True)
        self.assertIn(self.wh_a.in_type_id, types)
        self.assertIn(self.wh_b.in_type_id, types)

    def test_picking_type_search_keeps_warehouseless_types(self):
        picking_type = self._make_warehouseless_picking_type()
        self.assertIn(picking_type, self._searched_types(self.user_a, restrict=True))
```

`test_picking_type_search_not_filtered_without_warehouses` fija la decisión del spec: si el usuario no tiene almacenes cargados, el override no filtra. Quien realmente lo bloquea son las reglas de registro; filtrar acá solo produciría un desplegable vacío sin explicación.

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: FAIL en `test_picking_type_search_filters_with_context` — sin el override, el contexto se ignora y `user_a` ve los tipos de WH-B.

- [ ] **Step 3: Escribir la implementación**

`stock_warehouse_user_access/models/stock_picking_type.py`:

```python
from odoo import api, models
from odoo.osv import expression


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    @api.model
    def _get_user_warehouse_domain(self):
        """Dominio de tipos de operación visibles para el usuario actual.

        Devuelve una lista vacía cuando no corresponde filtrar: sin la clave de
        contexto, para usuarios eximidos, o para usuarios sin almacenes
        cargados (en ese caso el filtro real lo aplican las reglas de registro).
        """
        if not self.env.context.get('restrict_to_user_warehouses'):
            return []
        if self.env.user.has_group(
            'stock_warehouse_user_access.group_warehouse_access_all'
        ):
            return []
        warehouses = self.env.user.warehouse_access_ids
        if not warehouses:
            return []
        return [
            '|',
            ('warehouse_id', '=', False),
            ('warehouse_id', 'in', warehouses.ids),
        ]

    def _search(self, domain, offset=0, limit=None, order=None):
        warehouse_domain = self._get_user_warehouse_domain()
        if warehouse_domain:
            domain = expression.AND([domain, warehouse_domain])
        return super()._search(domain, offset=offset, limit=limit, order=order)
```

La firma replica exactamente la de `BaseModel._search` (`models.py:5798`). No se toca `read` ni `browse`: la maquinaria interna de rutas y reabastecimiento sigue accediendo a los tipos de operación de otros almacenes sin `AccessError`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: PASS los 5 tests de tipos de operación.

- [ ] **Step 5: Commit**

```bash
git add stock_warehouse_user_access/models/stock_picking_type.py stock_warehouse_user_access/tests/test_warehouse_access.py
git commit -m "feat(stock_warehouse_user_access): filtrado de tipos de operacion por contexto"
```

---

## Task 8: Activar el contexto en vistas y en el panel

**Files:**
- Create: `stock_warehouse_user_access/views/stock_picking_views.xml`
- Create: `stock_warehouse_user_access/views/purchase_order_views.xml`

- [ ] **Step 1: Crear la vista de albaranes y el override de la acción**

`stock_warehouse_user_access/views/stock_picking_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <record id="view_picking_form_warehouse_access" model="ir.ui.view">
            <field name="name">stock.picking.form.warehouse.access</field>
            <field name="model">stock.picking</field>
            <field name="inherit_id" ref="stock.view_picking_form"/>
            <field name="arch" type="xml">
                <xpath expr="//field[@name='picking_type_id']" position="attributes">
                    <attribute name="context">{'restrict_to_user_warehouses': True}</attribute>
                </xpath>
            </field>
        </record>

        <record id="stock.stock_picking_type_action" model="ir.actions.act_window">
            <field name="context">{'restrict_to_user_warehouses': True}</field>
        </record>

    </data>
</odoo>
```

Dos advertencias sobre este archivo:

1. El `xpath` usa `//field[@name='picking_type_id']`, que en `stock.view_picking_form` matchea el primero: el del formulario (línea 212 del archivo original). Si al actualizar Odoo el orden cambiara, el xpath podría apuntar a otro nodo; verificar en el Step 3 que el desplegable del formulario efectivamente filtra.
2. El segundo `record` **modifica una acción de otro módulo** (`stock`). El cambio persiste aunque se desinstale `stock_warehouse_user_access`. Es práctica estándar en Odoo, pero hay que saberlo: para revertirlo hay que actualizar el módulo `stock`. La acción nativa no define `context` (verificado en `addons/stock/views/stock_picking_type_views.xml:15-30`), así que no se está pisando ningún valor existente.

- [ ] **Step 2: Crear la vista de compras**

`stock_warehouse_user_access/views/purchase_order_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <record id="purchase_order_form_warehouse_access" model="ir.ui.view">
            <field name="name">purchase.order.form.warehouse.access</field>
            <field name="model">purchase.order</field>
            <field name="inherit_id" ref="purchase_stock.purchase_order_view_form_inherit"/>
            <field name="arch" type="xml">
                <xpath expr="//field[@name='picking_type_id']" position="attributes">
                    <attribute name="context">{'restrict_to_user_warehouses': True}</attribute>
                </xpath>
            </field>
        </record>

    </data>
</odoo>
```

El campo "Entregar a" que se está modificando lleva `groups="stock.group_stock_multi_locations"` en la vista nativa: solo es visible con ubicaciones múltiples activadas. El contexto se aplica igual, pero si el cliente no tiene esa opción activa el usuario ni siquiera ve el campo — en ese caso lo único que actúa es el valor por defecto de la Task 9.

- [ ] **Step 3: Actualizar y verificar a mano**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --stop-after-init
```
Expected: actualiza sin errores de validación de vistas.

Verificación manual, entrando con un usuario que tenga solo WH-A:
- Inventario → Resumen: solo aparecen las tarjetas de operación de WH-A.
- Inventario → nueva transferencia: el desplegable "Tipo de operación" solo lista los tipos de WH-A.
- Compras → nueva orden: el desplegable "Entregar a" solo lista los tipos de WH-A.

- [ ] **Step 4: Commit**

```bash
git add stock_warehouse_user_access/views/stock_picking_views.xml stock_warehouse_user_access/views/purchase_order_views.xml
git commit -m "feat(stock_warehouse_user_access): activar el filtro de almacen en vistas y panel"
```

---

## Task 9: Valores por defecto del tipo de operación

**Files:**
- Create: `stock_warehouse_user_access/models/purchase_order.py`
- Create: `stock_warehouse_user_access/models/stock_picking.py`
- Modify: `stock_warehouse_user_access/tests/test_warehouse_access.py`

**Por qué `default_get` y no `_default_picking_type`:** tanto `purchase.order.picking_type_id` como `stock.picking.picking_type_id` declaran su default pasando la **función** al atributo `default=` (`purchase_stock/models/purchase_order.py:23` y `stock/models/stock_picking.py:619`). Odoo guarda ese objeto función y lo invoca directamente, sin pasar por el MRO, así que redefinir el método en un `_inherit` no tendría ningún efecto sobre el valor por defecto. `default_get` sí se resuelve por herencia.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de la clase `TestWarehouseAccess`:

```python
    def test_purchase_default_picking_type_is_user_warehouse(self):
        defaults = self.env['purchase.order'].with_user(
            self.user_a
        ).default_get(['picking_type_id'])
        self.assertEqual(defaults.get('picking_type_id'), self.wh_a.in_type_id.id)

    def test_purchase_default_respects_explicit_context(self):
        defaults = self.env['purchase.order'].with_user(self.user_a).with_context(
            default_picking_type_id=self.wh_b.in_type_id.id
        ).default_get(['picking_type_id'])
        self.assertEqual(defaults.get('picking_type_id'), self.wh_b.in_type_id.id)

    def test_purchase_default_falls_back_without_default_warehouse(self):
        defaults = self.env['purchase.order'].with_user(
            self.user_none
        ).default_get(['picking_type_id'])
        self.assertTrue(defaults.get('picking_type_id'))

    def test_picking_default_picking_type_is_user_warehouse(self):
        defaults = self.env['stock.picking'].with_user(
            self.user_a
        ).default_get(['picking_type_id'])
        self.assertEqual(defaults.get('picking_type_id'), self.wh_a.int_type_id.id)

    def test_picking_default_respects_restricted_picking_type_code(self):
        defaults = self.env['stock.picking'].with_user(self.user_a).with_context(
            restricted_picking_type_code='incoming'
        ).default_get(['picking_type_id'])
        self.assertEqual(defaults.get('picking_type_id'), self.wh_a.in_type_id.id)
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: FAIL en `test_purchase_default_picking_type_is_user_warehouse` y `test_picking_default_picking_type_is_user_warehouse` — el default nativo devuelve el primer tipo de la compañía, que puede ser el de WH-B.

- [ ] **Step 3: Implementar el default de compras**

`stock_warehouse_user_access/models/purchase_order.py`:

```python
from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'picking_type_id' not in fields_list:
            return defaults
        if self.env.context.get('default_picking_type_id'):
            return defaults
        warehouse = self.env.user.default_warehouse_id
        if not warehouse or not warehouse.in_type_id:
            return defaults
        company_id = self.env.context.get('company_id') or self.env.company.id
        if warehouse.company_id.id != company_id:
            return defaults
        defaults['picking_type_id'] = warehouse.in_type_id.id
        return defaults
```

- [ ] **Step 4: Implementar el default de transferencias**

`stock_warehouse_user_access/models/stock_picking.py`:

```python
from odoo import api, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    _WAREHOUSE_TYPE_BY_CODE = {
        'incoming': 'in_type_id',
        'outgoing': 'out_type_id',
        'internal': 'int_type_id',
    }

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'picking_type_id' not in fields_list:
            return defaults
        if self.env.context.get('default_picking_type_id'):
            return defaults
        warehouse = self.env.user.default_warehouse_id
        if not warehouse:
            return defaults
        if warehouse.company_id.id != self.env.company.id:
            return defaults
        code = self.env.context.get('restricted_picking_type_code') or 'internal'
        field_name = self._WAREHOUSE_TYPE_BY_CODE.get(code)
        if not field_name:
            return defaults
        picking_type = warehouse[field_name]
        if picking_type:
            defaults['picking_type_id'] = picking_type.id
        return defaults
```

`restricted_picking_type_code` es la clave que el propio Odoo usa en `stock.picking._default_picking_type_id` (`stock/models/stock_picking.py:536-541`) cuando se entra desde los menús de Recepciones o Entregas. Respetarla es lo que hace que este override redirija al almacén del usuario sin cambiar el tipo de documento que el menú pidió.

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: PASS los 5 tests de valores por defecto.

- [ ] **Step 6: Commit**

```bash
git add stock_warehouse_user_access/models/purchase_order.py stock_warehouse_user_access/models/stock_picking.py stock_warehouse_user_access/tests/test_warehouse_access.py
git commit -m "feat(stock_warehouse_user_access): tipo de operacion por defecto segun el almacen del usuario"
```

---

## Task 10: `post_init_hook` de instalación

**Files:**
- Create: `stock_warehouse_user_access/hooks.py`
- Modify: `stock_warehouse_user_access/tests/test_warehouse_access.py`

**Por qué existe:** el módulo falla cerrado. Un usuario sin almacenes y sin el grupo de excepción no ve ningún documento con almacén. Sin este hook, instalar el módulo en producción deja a toda la gerencia con pantallas vacías hasta que alguien configure usuario por usuario.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de la clase `TestWarehouseAccess`:

```python
    def test_post_init_hook_exempts_existing_managers(self):
        from odoo.addons.stock_warehouse_user_access.hooks import post_init_hook

        manager = self.env['res.users'].create({
            'name': 'Gerente de stock',
            'login': 'gerente_stock_wh',
            'groups_id': [(6, 0, [self.env.ref('stock.group_stock_manager').id])],
        })
        plain = self.env['res.users'].create({
            'name': 'Operario',
            'login': 'operario_wh',
            'groups_id': [(6, 0, [self.env.ref('stock.group_stock_user').id])],
        })
        manager.write({'groups_id': [(3, self.group_all.id)]})
        plain.write({'groups_id': [(3, self.group_all.id)]})

        post_init_hook(self.env)

        self.assertIn(self.group_all, manager.groups_id)
        self.assertNotIn(self.group_all, plain.groups_id)
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: FAIL con `ModuleNotFoundError` / `ImportError` sobre `stock_warehouse_user_access.hooks`.

- [ ] **Step 3: Escribir el hook**

`stock_warehouse_user_access/hooks.py`:

```python
MANAGER_GROUP_XMLIDS = (
    'stock.group_stock_manager',
    'purchase.group_purchase_manager',
)


def post_init_hook(env):
    """Exime del filtro por almacén a los gerentes que ya existían.

    El módulo falla cerrado: sin almacenes cargados un usuario no ve ningún
    documento con almacén. Sin esto, instalar en producción dejaría a la
    gerencia sin acceso hasta configurar usuario por usuario.
    """
    group_all = env.ref(
        'stock_warehouse_user_access.group_warehouse_access_all',
        raise_if_not_found=False,
    )
    if not group_all:
        return

    manager_groups = env['res.groups']
    for xmlid in MANAGER_GROUP_XMLIDS:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            manager_groups |= group
    if not manager_groups:
        return

    users = env['res.users'].sudo().search([
        ('share', '=', False),
        ('groups_id', 'in', manager_groups.ids),
    ])
    if users:
        group_all.sudo().write({
            'users': [(4, user.id) for user in users],
        })
```

`post_init_hook` recibe un único argumento `env` en Odoo 18 (verificado en `odoo/modules/loading.py:244-246`). El comando `(4, id)` es idempotente: agregar un usuario que ya está en el grupo no hace nada.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run:
```bash
odoo -d <db> -u stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: PASS el test del hook.

- [ ] **Step 5: Commit**

```bash
git add stock_warehouse_user_access/hooks.py stock_warehouse_user_access/tests/test_warehouse_access.py
git commit -m "feat(stock_warehouse_user_access): hook de instalacion que exime a gerentes existentes"
```

---

## Task 11: Verificación completa e instalación limpia

**Files:**
- Create: `stock_warehouse_user_access/README.md`

- [ ] **Step 1: Instalación desde cero en base limpia**

Este es el único paso que ejercita el `post_init_hook`, que solo corre en instalaciones nuevas (`new_install`), nunca en actualizaciones.

Run:
```bash
odoo -d <db_limpia> -i stock_warehouse_user_access --test-enable --stop-after-init
```
Expected: instala sin error y pasan los 21 tests de `TestWarehouseAccess`.

- [ ] **Step 2: Verificar que el administrador no quedó encerrado**

Run:
```bash
odoo shell -d <db_limpia> --no-http
```

En el shell:
```python
admin = env.ref('base.user_admin')
group = env.ref('stock_warehouse_user_access.group_warehouse_access_all')
print(group in admin.groups_id)
```
Expected: `True`. El usuario `admin` pertenece de fábrica a `stock.group_stock_manager` y a `purchase.group_purchase_manager`, así que el hook lo exime.

- [ ] **Step 3: Escribir el README**

`stock_warehouse_user_access/README.md`:

```markdown
# Acceso por Almacén

Limita la visibilidad de transferencias y órdenes de compra al almacén asignado
a cada usuario, sin impedir las transferencias entre almacenes.

## Configuración

En Ajustes → Usuarios, pestaña "Permisos de acceso", sección "Acceso por Almacén":

- **Almacenes permitidos**: almacenes cuyos documentos ve el usuario.
- **Almacén por defecto**: el que se propone al crear una transferencia o una
  orden de compra. Debe estar dentro de los permitidos.
- **Ver todos los almacenes**: exime al usuario del filtro.

## Comportamiento

- **Transferencias**: el usuario ve un albarán si el tipo de operación, la
  ubicación origen o la ubicación destino pertenecen a alguno de sus almacenes.
  Por eso una transferencia entre almacenes es visible desde las dos puntas.
- **Compras**: ve solo las órdenes cuyo "Entregar a" apunta a un almacén suyo.
  Las órdenes sin almacén (servicios, dropship) son visibles para todos.
- **Desplegables**: el tipo de operación de las transferencias, el "Entregar a"
  de las compras y el panel Resumen de Inventario listan solo los almacenes del
  usuario.

## Advertencias

- **Falla cerrado.** Un usuario sin almacenes cargados y sin el permiso "Ver
  todos los almacenes" no ve ningún documento que tenga almacén. Al instalar, el
  módulo le otorga ese permiso a quienes ya sean gerente de inventario o
  administrador de compras; el resto hay que configurarlo a mano.
- **El filtro de los desplegables es de interfaz, no de seguridad.** Vía
  importación o API se puede apuntar a otro almacén; el documento resultante
  simplemente desaparecerá de la vista del usuario por las reglas de registro.
- El módulo modifica el contexto de la acción `stock.stock_picking_type_action`.
  Ese cambio persiste después de desinstalar.

## Fuera de alcance

Líneas de orden de compra, reporte de compras, existencias, ajustes de
inventario, ventas y POS.
```

- [ ] **Step 4: Commit**

```bash
git add stock_warehouse_user_access/README.md
git commit -m "docs(stock_warehouse_user_access): readme de configuracion y advertencias"
```

---

## Cobertura del spec

| Sección del spec | Task |
|---|---|
| Campos `warehouse_access_ids` / `default_warehouse_id` + constraint | 3 |
| Grupo `group_warehouse_access_all` | 2 |
| Par de reglas de `stock.picking` | 5 |
| Par de reglas de `purchase.order` | 6 |
| Anclaje en `base.group_user` | 5 |
| `_search` de `stock.picking.type` por contexto | 7 |
| Contexto en formulario de compras, de albarán y panel Resumen | 8 |
| Valores por defecto del tipo de operación | 9 |
| `post_init_hook` | 10 |
| Vista del formulario de usuario | 4 |
| Los 10 casos de test del spec | 3, 5, 6, 7, 9 (21 tests en total) |
