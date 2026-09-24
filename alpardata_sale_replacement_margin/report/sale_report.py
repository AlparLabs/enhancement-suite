from __future__ import annotations

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    replacement_margin = fields.Float(string='Margen de reposición')

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['replacement_margin'] = f"""SUM(l.replacement_margin
            / {self._case_value_or_one('s.currency_rate')}
            * {self._case_value_or_one('account_currency_table.rate')})
        """
        return res
