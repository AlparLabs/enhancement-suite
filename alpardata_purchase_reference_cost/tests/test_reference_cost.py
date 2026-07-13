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
