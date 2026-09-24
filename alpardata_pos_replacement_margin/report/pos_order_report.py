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
