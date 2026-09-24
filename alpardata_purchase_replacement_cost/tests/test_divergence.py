from __future__ import annotations

from odoo.tests import tagged

from .common import ReplacementCostCommon


@tagged('post_install', '-at_install')
class TestDivergenceNetCost(ReplacementCostCommon):

    def test_avco_equal_to_net_is_ok(self):
        self._set_partner_conditions()
        self._add_seller()
        self.template.standard_price = 829.35
        self.assertEqual(self.template.cost_divergence_alert, 'ok')
        self.assertAlmostEqual(self.template.cost_divergence_pct, 0.0, places=2)

    def test_without_cascade_compares_to_list(self):
        self._set_partner_conditions(cascade='')
        self._add_seller()
        self.template.standard_price = 1000.0
        self.assertEqual(self.template.cost_divergence_alert, 'ok')
