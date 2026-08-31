from __future__ import annotations

from odoo import fields
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

    def test_unsaved_sellers_do_not_break_sort(self):
        """Regresión: proveedores sin guardar (onchange) no rompen el orden.

        En un onchange las líneas nuevas tienen id de tipo NewId. Si dos empatan
        en (empresa, sequence), el sort los comparaba y fallaba con
        'TypeError: < not supported between instances of NewId and NewId'.
        """
        form_template = self.env['product.template'].new({'name': 'Producto Onchange'})
        for _ in range(2):
            form_template.seller_ids = [
                (0, 0, {
                    'partner_id': self.partner.id,
                    'reference_cost': 100.0,
                    'sequence': 10,
                }),
            ]
        # No debe lanzar TypeError al resolver el proveedor.
        self.assertEqual(form_template.reference_cost, 100.0)

    def test_product_template_reference_cost_uom_conversion(self):
        """product.template.reference_cost se expresa siempre en la UoM base del
        producto (uom_id), convirtiendo desde la UoM del proveedor (product_uom_id)."""
        uom_unit = self.env['uom.uom'].create({'name': 'Unidad Test Tmpl'})
        uom_pack24 = self.env['uom.uom'].create({
            'name': 'Pack x 24 Tmpl',
            'relative_uom_id': uom_unit.id,
            'relative_factor': 24.0,
        })
        product = self.env['product.product'].create({
            'name': 'Producto Pack UoM',
            'uom_id': uom_unit.id,
            'standard_price': 200.0,
        })
        self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_uom_id': uom_pack24.id,
            'reference_cost': 4800.0,
        })
        # 4800 / 24 = 200.0 en la unidad base
        self.assertEqual(product.product_tmpl_id.reference_cost, 200.0)
        # La divergencia AVCO (200 vs 200) debe ser 0% ('ok')
        self.assertEqual(product.product_tmpl_id.cost_divergence_pct, 0.0)
        self.assertEqual(product.product_tmpl_id.cost_divergence_alert, 'ok')

    def test_cost_schedule_round_trip_with_vendor_uom(self):
        """Programar un costo cargado en la unidad del producto no cambia de escala.

        El formulario de programacion muestra `current_reference_cost` en la
        unidad del producto, porque sale de `product.template.reference_cost`.
        La ficha de proveedor guarda el costo en su unidad de compra, asi que
        al aplicar hay que convertir: sin eso, un costo cargado por unidad se
        guardaba como precio por bulto y el costo de referencia saltaba x24.
        """
        uom_unit = self.env['uom.uom'].create({'name': 'Unidad Programacion'})
        uom_pack24 = self.env['uom.uom'].create({
            'name': 'Pack x 24 Programacion',
            'relative_uom_id': uom_unit.id,
            'relative_factor': 24.0,
        })
        product = self.env['product.product'].create({
            'name': 'Producto Programacion',
            'uom_id': uom_unit.id,
        })
        tmpl = product.product_tmpl_id
        self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_tmpl_id': tmpl.id,
            'product_uom_id': uom_pack24.id,
            'reference_cost': 2400.0,
        })
        self.assertEqual(tmpl.reference_cost, 100.0)

        schedule = self.env['product.cost.schedule'].create({
            'name': 'Suba programada',
            'product_tmpl_id': tmpl.id,
            'new_reference_cost': 120.0,
            'effective_date': fields.Date.today(),
        })
        # El form muestra el costo actual en la unidad del producto.
        self.assertEqual(schedule.current_reference_cost, 100.0)

        schedule.action_apply_now()

        # Y el nuevo costo se lee en la misma unidad en la que se cargo.
        self.assertEqual(schedule.state, 'done')
        self.assertEqual(tmpl.reference_cost, 120.0)
        # En la ficha de proveedor quedo guardado por bulto: 120 x 24.
        new_seller = tmpl.seller_ids.filtered(
            lambda s: s.date_start == schedule.effective_date
        )
        self.assertEqual(new_seller.product_uom_id, uom_pack24)
        self.assertEqual(new_seller.reference_cost, 2880.0)
