# Purchase Minimum Approval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el módulo `purchase_minimum_approval` que bloquea la confirmación de órdenes de compra por debajo del mínimo configurado por proveedor, con un flujo de aprobación por grupo.

**Architecture:** Espejo del módulo `sale_credit_limit_approval`. Campos en `res.partner` (aplica mínimo + monto en moneda de compañía), estado nuevo `waiting_approval` en `purchase.order` vía `selection_add`, override de `button_confirm` que compara `amount_untaxed` (convertido a moneda de compañía) contra el mínimo, y botón de aprobación visible solo para el grupo aprobador.

**Tech Stack:** Odoo 18.0, Python, XML views, `TransactionCase` tests.

**Referencia de patrón:** `sale_credit_limit_approval/` en la raíz del repo.

---

## File Structure

```
purchase_minimum_approval/
├── __init__.py                       # import models
├── __manifest__.py                   # depends ['purchase'], version 18.0.1.0.0
├── models/
│   ├── __init__.py                   # import res_partner, purchase_order
│   ├── res_partner.py                # apply_purchase_minimum, purchase_minimum_amount
│   └── purchase_order.py             # estado, chequeo, confirm, aprobación, cancel
├── security/
│   └── security.xml                  # group_purchase_minimum_approver
├── views/
│   ├── res_partner_views.xml         # campos en pestaña Compras
│   └── purchase_order_views.xml      # banner, nota, botón, statusbar
└── tests/
    ├── __init__.py
    └── test_purchase_minimum.py
```

Responsabilidades:
- `res_partner.py`: solo definición de los dos campos de configuración.
- `purchase_order.py`: toda la lógica de negocio (chequeo, transición de estado, aprobación, cancelación, campos computados de UI).
- `security.xml`: el grupo aprobador.
- Vistas separadas por modelo.

---

## Task 1: Scaffolding del módulo (manifest + init)

**Files:**
- Create: `purchase_minimum_approval/__init__.py`
- Create: `purchase_minimum_approval/__manifest__.py`
- Create: `purchase_minimum_approval/models/__init__.py`

- [ ] **Step 1: Crear `__init__.py` raíz**

`purchase_minimum_approval/__init__.py`:
```python
from . import models
```

- [ ] **Step 2: Crear `models/__init__.py`**

`purchase_minimum_approval/models/__init__.py`:
```python
from . import res_partner
from . import purchase_order
```

- [ ] **Step 3: Crear `__manifest__.py`**

`purchase_minimum_approval/__manifest__.py`:
```python
{
    'name': 'Purchase Minimum Approval',
    'version': '18.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Bloquea la confirmación de compras por debajo del mínimo del proveedor',
    'description': """
        Este módulo extiende el flujo de confirmación de órdenes de compra.
        Si el subtotal de la orden no alcanza el mínimo de compra configurado
        en el proveedor, la orden queda en estado 'Esperando Aprobación' y debe
        ser autorizada por un miembro del grupo aprobador de compras.

        Análogo al límite de crédito de ventas, pero para compras.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'purchase',
    ],
    'data': [
        'security/security.xml',
        'views/purchase_order_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

- [ ] **Step 4: Commit**

```bash
git add purchase_minimum_approval/__init__.py purchase_minimum_approval/__manifest__.py purchase_minimum_approval/models/__init__.py
git commit -m "feat(purchase_minimum_approval): scaffolding del modulo"
```

---

## Task 2: Campos en `res.partner`

**Files:**
- Create: `purchase_minimum_approval/models/res_partner.py`

- [ ] **Step 1: Crear el modelo**

`purchase_minimum_approval/models/res_partner.py`:
```python
# purchase_minimum_approval/models/res_partner.py
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    apply_purchase_minimum = fields.Boolean(
        string='Aplica mínimo de compra',
        help='Si está activo, las órdenes de compra a este proveedor por debajo '
             'del mínimo quedarán pendientes de aprobación.',
        tracking=True,
    )
    purchase_minimum_amount = fields.Monetary(
        string='Mínimo de compra',
        currency_field='currency_id',
        help='Monto mínimo (subtotal sin impuestos, en moneda de la compañía) '
             'requerido para confirmar una orden de compra a este proveedor.',
        tracking=True,
    )
```

Nota: `currency_id` ya existe en `res.partner` (moneda de la compañía por defecto).

- [ ] **Step 2: Instalar el módulo y verificar que los campos existen**

Run (ajustar DB/rutas al entorno):
```bash
odoo -d <db> -i purchase_minimum_approval --stop-after-init
```
Expected: instala sin error; los campos `apply_purchase_minimum` y `purchase_minimum_amount` quedan creados en `res.partner`.

- [ ] **Step 3: Commit**

```bash
git add purchase_minimum_approval/models/res_partner.py
git commit -m "feat(purchase_minimum_approval): campos de minimo en res.partner"
```

---

## Task 3: Grupo de seguridad

**Files:**
- Create: `purchase_minimum_approval/security/security.xml`

- [ ] **Step 1: Crear el grupo**

`purchase_minimum_approval/security/security.xml`:
```xml
<odoo>
    <data>
        <record id="group_purchase_minimum_approver" model="res.groups">
            <field name="name">Compras: Aprobar Mínimo de Compra</field>
            <field name="category_id" ref="base.module_category_inventory_purchase"/>
            <field name="implied_ids" eval="[(4, ref('purchase.group_purchase_user'))]"/>
            <field name="comment">Permite aprobar órdenes de compra que no alcanzan el mínimo del proveedor.</field>
        </record>
    </data>
</odoo>
```

- [ ] **Step 2: Actualizar el módulo y verificar el grupo**

Run:
```bash
odoo -d <db> -u purchase_minimum_approval --stop-after-init
```
Expected: instala sin error; el grupo aparece en Ajustes → Usuarios → Grupos.

- [ ] **Step 3: Commit**

```bash
git add purchase_minimum_approval/security/security.xml
git commit -m "feat(purchase_minimum_approval): grupo aprobador de minimo"
```

---

## Task 4: Lógica en `purchase.order` (TDD)

**Files:**
- Create: `purchase_minimum_approval/models/purchase_order.py`
- Create: `purchase_minimum_approval/tests/__init__.py`
- Create: `purchase_minimum_approval/tests/test_purchase_minimum.py`

- [ ] **Step 1: Escribir los tests (fallan)**

`purchase_minimum_approval/tests/__init__.py`:
```python
from . import test_purchase_minimum
```

`purchase_minimum_approval/tests/test_purchase_minimum.py`:
```python
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestPurchaseMinimum(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.product = cls.env['product.product'].create({
            'name': 'Producto test',
            'purchase_method': 'purchase',
        })
        cls.approver_group = cls.env.ref(
            'purchase_minimum_approval.group_purchase_minimum_approver'
        )
        cls.approver = cls.env['res.users'].create({
            'name': 'Aprobador',
            'login': 'aprobador_min',
            'groups_id': [(6, 0, [cls.approver_group.id])],
        })
        cls.buyer = cls.env['res.users'].create({
            'name': 'Comprador',
            'login': 'comprador_min',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])],
        })

    def _make_partner(self, apply_minimum=False, minimum=0.0, parent=None):
        return self.env['res.partner'].create({
            'name': 'Proveedor test',
            'apply_purchase_minimum': apply_minimum,
            'purchase_minimum_amount': minimum,
            'parent_id': parent.id if parent else False,
        })

    def _make_po(self, partner, qty=1, price=100.0):
        return self.env['purchase.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'product_qty': qty,
                'price_unit': price,
                'product_uom': self.product.uom_id.id,
                'date_planned': '2026-07-20 00:00:00',
            })],
        })

    def test_no_minimum_confirms(self):
        partner = self._make_partner(apply_minimum=False)
        po = self._make_po(partner, price=10.0)
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_above_minimum_confirms(self):
        partner = self._make_partner(apply_minimum=True, minimum=50.0)
        po = self._make_po(partner, price=100.0)  # subtotal 100 >= 50
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_below_minimum_blocks(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)  # subtotal 100 < 500
        po.button_confirm()
        self.assertEqual(po.state, 'waiting_approval')
        self.assertTrue(po.minimum_approval_note)

    def test_approver_approves(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)
        po.button_confirm()
        self.assertEqual(po.state, 'waiting_approval')
        po.with_user(self.approver).action_approve_minimum()
        self.assertEqual(po.state, 'purchase')

    def test_non_approver_cannot_approve(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)
        po.button_confirm()
        with self.assertRaises(AccessError):
            po.with_user(self.buyer).action_approve_minimum()

    def test_parent_minimum_applies_to_child(self):
        parent = self._make_partner(apply_minimum=True, minimum=500.0)
        child = self._make_partner(apply_minimum=False, parent=parent)
        po = self._make_po(child, price=100.0)
        po.button_confirm()
        self.assertEqual(po.state, 'waiting_approval')

    def test_cancel_waiting_approval(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)
        po.button_confirm()
        po.button_cancel()
        self.assertEqual(po.state, 'cancel')
```

- [ ] **Step 2: Ejecutar tests, verificar que fallan**

Run:
```bash
odoo -d <db> -i purchase_minimum_approval --test-enable --stop-after-init
```
Expected: fallan por atributos/métodos inexistentes (`minimum_approval_note`, `action_approve_minimum`, estado `waiting_approval`).

- [ ] **Step 3: Implementar `purchase_order.py`**

`purchase_minimum_approval/models/purchase_order.py`:
```python
# purchase_minimum_approval/models/purchase_order.py
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(
        selection_add=[
            ('waiting_approval', 'Esperando Aprobación'),
        ],
        ondelete={'waiting_approval': 'set default'},
    )

    minimum_approval_note = fields.Char(
        string='Nota de Mínimo de Compra',
        readonly=True,
        copy=False,
    )

    purchase_minimum_warning = fields.Char(
        string='Advertencia de mínimo de compra',
        compute='_compute_purchase_minimum_warning',
    )

    show_approve_minimum_button = fields.Boolean(
        string='Mostrar botón de aprobación de mínimo',
        compute='_compute_show_approve_minimum_button',
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_minimum_partner(self):
        self.ensure_one()
        return self.partner_id.commercial_partner_id

    def _amount_untaxed_company_currency(self):
        """Subtotal de la orden convertido a la moneda de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        order_currency = self.currency_id or company.currency_id
        return order_currency._convert(
            self.amount_untaxed,
            company.currency_id,
            company,
            self.date_order or fields.Date.context_today(self),
        )

    def _check_purchase_minimum(self):
        """True si la orden queda por debajo del mínimo del proveedor."""
        self.ensure_one()
        partner = self._get_minimum_partner()
        if not partner.apply_purchase_minimum or partner.purchase_minimum_amount <= 0:
            return False
        company_currency = (self.company_id or self.env.company).currency_id
        subtotal = self._amount_untaxed_company_currency()
        # subtotal < minimo  ->  -1
        return float_compare(
            subtotal,
            partner.purchase_minimum_amount,
            precision_rounding=company_currency.rounding,
        ) < 0

    # -------------------------------------------------------------------------
    # Confirmación
    # -------------------------------------------------------------------------
    def button_confirm(self):
        if self.env.context.get('bypass_purchase_minimum'):
            return super().button_confirm()

        to_confirm = self.env['purchase.order']

        for order in self:
            if order.state not in ('draft', 'sent'):
                to_confirm |= order
                continue
            if order._check_purchase_minimum():
                partner = order._get_minimum_partner()
                company_currency = (order.company_id or self.env.company).currency_id
                minimum = partner.purchase_minimum_amount
                subtotal = order._amount_untaxed_company_currency()
                note = _(
                    "Requiere aprobación. Mínimo: %(min)s %(cur)s | "
                    "Subtotal orden: %(sub)s %(cur)s",
                    min=minimum,
                    sub=round(subtotal, 2),
                    cur=company_currency.name,
                )
                order.write({
                    'state': 'waiting_approval',
                    'minimum_approval_note': note,
                })
                order.message_post(
                    body=_(
                        "⚠️ Orden bloqueada: no alcanza el mínimo de compra del "
                        "proveedor.\n%(note)s",
                        note=note,
                    ),
                    message_type='notification',
                )
            else:
                to_confirm |= order

        if to_confirm:
            return super(PurchaseOrder, to_confirm).button_confirm()
        return True

    # -------------------------------------------------------------------------
    # Aprobación
    # -------------------------------------------------------------------------
    def action_approve_minimum(self):
        self.ensure_one()
        approver_group = self.env.ref(
            'purchase_minimum_approval.group_purchase_minimum_approver'
        )
        if approver_group not in self.env.user.groups_id:
            raise AccessError(_(
                "No tiene permiso para aprobar el mínimo de compra. "
                "Se requiere pertenecer al grupo aprobador de compras."
            ))
        if self.state != 'waiting_approval':
            raise UserError(_("Esta orden no está pendiente de aprobación de mínimo."))

        self.message_post(
            body=_(
                "✅ Mínimo de compra aprobado por %(user)s. La orden procede a confirmarse.",
                user=self.env.user.name,
            ),
            message_type='notification',
        )
        self.write({'state': 'draft', 'minimum_approval_note': False})
        return self.with_context(bypass_purchase_minimum=True).button_confirm()

    # -------------------------------------------------------------------------
    # Cancelación
    # -------------------------------------------------------------------------
    def button_cancel(self):
        waiting = self.filtered(lambda o: o.state == 'waiting_approval')
        if waiting:
            waiting.write({'state': 'cancel', 'minimum_approval_note': False})
        remaining = self - waiting
        if remaining:
            return super(PurchaseOrder, remaining).button_cancel()
        return True

    # -------------------------------------------------------------------------
    # Campos computados de UI
    # -------------------------------------------------------------------------
    @api.depends(
        'state', 'amount_untaxed', 'currency_id',
        'partner_id.commercial_partner_id.apply_purchase_minimum',
        'partner_id.commercial_partner_id.purchase_minimum_amount',
    )
    def _compute_purchase_minimum_warning(self):
        for order in self:
            warning = ''
            if order.state in ('draft', 'sent') and order._check_purchase_minimum():
                partner = order._get_minimum_partner()
                company_currency = (order.company_id or self.env.company).currency_id
                warning = _(
                    "Este proveedor exige un mínimo de compra de %(min)s %(cur)s "
                    "(subtotal actual: %(sub)s %(cur)s). Al confirmar, la orden "
                    "quedará pendiente de aprobación.",
                    min=partner.purchase_minimum_amount,
                    sub=round(order._amount_untaxed_company_currency(), 2),
                    cur=company_currency.name,
                )
            order.purchase_minimum_warning = warning

    def _compute_show_approve_minimum_button(self):
        approver_group = self.env.ref(
            'purchase_minimum_approval.group_purchase_minimum_approver'
        )
        is_approver = approver_group in self.env.user.groups_id
        for order in self:
            order.show_approve_minimum_button = bool(
                order.state == 'waiting_approval' and is_approver
            )
```

- [ ] **Step 4: Ejecutar tests, verificar que pasan**

Run:
```bash
odoo -d <db> -u purchase_minimum_approval --test-enable --stop-after-init
```
Expected: los 7 tests de `TestPurchaseMinimum` pasan.

- [ ] **Step 5: Commit**

```bash
git add purchase_minimum_approval/models/purchase_order.py purchase_minimum_approval/tests/
git commit -m "feat(purchase_minimum_approval): logica de bloqueo y aprobacion en purchase.order"
```

---

## Task 5: Vista del proveedor

**Files:**
- Create: `purchase_minimum_approval/views/res_partner_views.xml`

- [ ] **Step 1: Crear la vista**

`purchase_minimum_approval/views/res_partner_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!--
        Agrega los campos de mínimo de compra en la pestaña Compras del
        formulario de contacto (account.view_partner_property_form incluye la
        sección de compras en Odoo 18).
    -->
    <record id="view_partner_form_purchase_minimum" model="ir.ui.view">
        <field name="name">res.partner.form.purchase.minimum</field>
        <field name="model">res.partner</field>
        <field name="inherit_id" ref="account.view_partner_property_form"/>
        <field name="arch" type="xml">

            <xpath expr="//page[@id='purchase']//field[@name='property_purchase_currency_id']" position="after">
                <field name="apply_purchase_minimum"/>
                <field
                    name="purchase_minimum_amount"
                    invisible="not apply_purchase_minimum"
                />
            </xpath>

        </field>
    </record>
</odoo>
```

Nota de verificación: confirmar el `expr` contra la estructura real de
`account.view_partner_property_form`. Si `property_purchase_currency_id` no
existe en la instalación, usar como ancla el nodo de la página de compras:
`//page[@name='purchase']` con `position="inside"`. Verificar en Step 2.

- [ ] **Step 2: Actualizar módulo y verificar la vista**

Run:
```bash
odoo -d <db> -u purchase_minimum_approval --stop-after-init
```
Expected: actualiza sin error de vista. Abrir un contacto → pestaña Compras →
se ven "Aplica mínimo de compra" y "Mínimo de compra" (este último solo con el
check activo). Si hay error de XPath, ajustar el ancla según la nota del Step 1.

- [ ] **Step 3: Commit**

```bash
git add purchase_minimum_approval/views/res_partner_views.xml
git commit -m "feat(purchase_minimum_approval): campos de minimo en vista de proveedor"
```

---

## Task 6: Vista de la orden de compra

**Files:**
- Create: `purchase_minimum_approval/views/purchase_order_views.xml`

- [ ] **Step 1: Crear la vista**

`purchase_minimum_approval/views/purchase_order_views.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_purchase_order_form_minimum_approval" model="ir.ui.view">
        <field name="name">purchase.order.form.minimum.approval</field>
        <field name="model">purchase.order</field>
        <field name="inherit_id" ref="purchase.purchase_order_form"/>
        <field name="arch" type="xml">

            <!-- Botón de aprobación en el header -->
            <xpath expr="//header/button[@name='button_confirm']" position="before">
                <button
                    name="action_approve_minimum"
                    string="Aprobar Mínimo"
                    type="object"
                    class="btn-success"
                    invisible="state != 'waiting_approval' or not show_approve_minimum_button"
                    confirm="¿Aprobar el mínimo de compra y confirmar esta orden?"
                />
            </xpath>

            <!-- Estado nuevo en la barra de estados -->
            <xpath expr="//header/field[@name='state']" position="attributes">
                <attribute name="statusbar_visible">draft,sent,waiting_approval,purchase,done</attribute>
            </xpath>

            <!-- Banner de advertencia (borrador) + nota (esperando aprobación) -->
            <xpath expr="//sheet" position="before">
                <div
                    class="alert alert-warning mb-0"
                    invisible="not purchase_minimum_warning"
                    role="alert"
                >
                    <i class="fa fa-exclamation-triangle me-2"/>
                    <field name="purchase_minimum_warning" readonly="1"/>
                </div>
                <div
                    class="alert alert-danger mb-0"
                    invisible="state != 'waiting_approval'"
                    role="alert"
                >
                    <i class="fa fa-lock me-2"/>
                    <strong>Orden pendiente de aprobación de mínimo de compra.</strong>
                    <field name="minimum_approval_note" readonly="1" class="d-block mt-1"/>
                </div>
            </xpath>

            <!-- Campos invisibles necesarios para las expresiones -->
            <xpath expr="//field[@name='state']" position="before">
                <field name="show_approve_minimum_button" invisible="1"/>
            </xpath>

        </field>
    </record>
</odoo>
```

- [ ] **Step 2: Actualizar módulo y verificar la vista**

Run:
```bash
odoo -d <db> -u purchase_minimum_approval --stop-after-init
```
Expected: actualiza sin error. Crear una orden a un proveedor con mínimo alto y
subtotal bajo → aparece el banner amarillo en borrador; al confirmar pasa a
"Esperando Aprobación" con banner rojo; un usuario del grupo aprobador ve el
botón "Aprobar Mínimo".

- [ ] **Step 3: Commit**

```bash
git add purchase_minimum_approval/views/purchase_order_views.xml
git commit -m "feat(purchase_minimum_approval): vista de orden con banner y boton de aprobacion"
```

---

## Task 7: Verificación final e i18n

**Files:**
- Create (si corresponde): `purchase_minimum_approval/i18n/es.po`

- [ ] **Step 1: Correr toda la suite de tests una vez más**

Run:
```bash
odoo -d <db> -u purchase_minimum_approval --test-enable --stop-after-init
```
Expected: todos los tests pasan, sin errores de carga de vistas.

- [ ] **Step 2: Revisar i18n**

Como los strings de código y vistas ya están en español (idioma destino del
usuario), NO se requiere `es.po`. Confirmar que no quedó ningún string en
inglés visible al usuario. Si aparece alguno, agregarlo a `i18n/es.po` y
declararlo en el manifest. (Ver memoria: los strings en inglés requieren
es.po/es_AR.po; acá el default es español, así que normalmente no aplica.)

- [ ] **Step 3: Commit final (si hubo cambios de i18n)**

```bash
git add purchase_minimum_approval/i18n/
git commit -m "chore(purchase_minimum_approval): traducciones es"
```

---

## Notas de verificación durante la ejecución

- **XPath del partner (Task 5):** el ancla exacta depende de la estructura de
  `account.view_partner_property_form` en la instancia. Si falla, usar
  `//page[@name='purchase']` con `position="inside"`.
- **`purchase_method` en el producto (tests):** se setea a `'purchase'` para
  evitar dependencias de recepción; ajustar si el producto de test necesita
  otra config.
- **Conversión de moneda:** los tests corren en la moneda de la compañía por
  defecto, así que la conversión es identidad; el test `test_below_minimum_blocks`
  cubre la comparación. La conversión real solo importa con órdenes en otra
  moneda (fuera del set mínimo de tests, cubierto por la lógica).
