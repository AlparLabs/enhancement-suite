from __future__ import annotations

from odoo import fields
from odoo.tests import tagged

from .common import ReplacementCostCommon


@tagged('post_install', '-at_install')
class TestTemplateReplacementCost(ReplacementCostCommon):

    def test_canonical_example(self):
        self._set_partner_conditions()
        self._add_seller()
        self.assertAlmostEqual(self.template.reference_cost, 1000.0)
        self.assertAlmostEqual(self.template.net_purchase_cost, 829.35, delta=0.01)
        self.assertAlmostEqual(self.template.replacement_cost, 854.23, delta=0.01)

    def test_internal_tax_adds_on_net(self):
        self._set_partner_conditions(early=0, freight=0, perception=0)
        self.template.internal_tax_pct = 10.0
        self._add_seller()
        self.assertAlmostEqual(self.template.replacement_cost, 829.35 * 1.10, delta=0.01)

    def test_no_seller_is_zero(self):
        self.assertEqual(self.template.replacement_cost, 0.0)
        self.assertEqual(self.template.net_purchase_cost, 0.0)

    def test_uom_pack(self):
        """Lista por pack de 24 → reposición por unidad."""
        self._set_partner_conditions(cascade='', early=0, freight=0, perception=0)
        uom_unit = self.env.ref('uom.product_uom_unit')
        pack = self.env['uom.uom'].create({
            'name': 'Pack x24 Test',
            'relative_factor': 24.0,
            'relative_uom_id': uom_unit.id,
        })
        self._add_seller(reference_cost=2400.0, product_uom_id=pack.id)
        self.assertAlmostEqual(self.template.replacement_cost, 100.0, places=4)

    def test_currency_usd(self):
        self._set_partner_conditions(cascade='', early=0, freight=0, perception=0)
        usd = self.env.ref('base.USD')
        usd.active = True
        company_currency = self.env.company.currency_id
        if company_currency == usd:
            self.skipTest('La empresa de test ya usa USD')
        self.env['res.currency.rate'].create({
            'currency_id': usd.id,
            'company_id': self.env.company.id,
            'name': fields.Date.today(),
            # 1 moneda-empresa = 0.001 USD → 1 USD = 1000 moneda-empresa
            'rate': 0.001,
        })
        self._add_seller(reference_cost=2.0, currency_id=usd.id)
        self.assertAlmostEqual(self.template.replacement_cost, 2000.0, places=2)

    def test_get_replacement_cost_for_fallback(self):
        cost, is_fallback = self.product._get_replacement_cost_for(
            self.env.company, self.product.uom_id, self.env.company.currency_id,
            fields.Date.today(),
        )
        self.assertTrue(is_fallback)
        self.assertEqual(cost, 800.0)

    def test_get_replacement_cost_for_uom(self):
        self._set_partner_conditions()
        self._add_seller()
        dozen = self.env.ref('uom.product_uom_dozen')
        cost, is_fallback = self.product._get_replacement_cost_for(
            self.env.company, dozen, self.env.company.currency_id, fields.Date.today(),
        )
        self.assertFalse(is_fallback)
        self.assertAlmostEqual(cost, 854.23 * 12, delta=0.12)
