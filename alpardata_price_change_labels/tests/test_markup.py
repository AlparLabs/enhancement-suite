from __future__ import annotations

from odoo.tests import tagged

from .common import PriceWatchCommon


@tagged('post_install', '-at_install')
class TestTargetMarkup(PriceWatchCommon):

    def test_target_from_category(self):
        self.assertEqual(self.template.target_markup_pct, 40.0)

    def test_target_manual_override(self):
        self.template.target_markup_pct = 30.0
        self.assertEqual(self.template.target_markup_pct, 30.0)
