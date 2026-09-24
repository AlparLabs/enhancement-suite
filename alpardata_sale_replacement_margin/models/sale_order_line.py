from __future__ import annotations

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    replacement_cost_unit = fields.Float(
        string='Costo de reposición',
        compute='_compute_replacement_cost_unit',
        store=True,
        precompute=True,
        copy=False,
        min_display_digits='Product Price',
        groups='base.group_user',
        help='Costo de reposición unitario al cargar la línea; se actualiza al confirmar.',
    )
    replacement_cost_fallback = fields.Boolean(
        string='Costo AVCO (sin reposición)',
        compute='_compute_replacement_cost_unit',
        store=True,
        precompute=True,
        copy=False,
        groups='base.group_user',
    )
    replacement_margin = fields.Float(
        string='Margen de reposición',
        compute='_compute_replacement_margin',
        store=True,
        digits='Product Price',
        groups='base.group_user',
    )
    replacement_margin_percent = fields.Float(
        string='Margen de reposición (%)',
        compute='_compute_replacement_margin',
        store=True,
        groups='base.group_user',
    )

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom_id')
    def _compute_replacement_cost_unit(self) -> None:
        for line in self:
            if not line.product_id:
                line.replacement_cost_unit = 0.0
                line.replacement_cost_fallback = False
                continue
            company = line.company_id or self.env.company
            date = line.order_id.date_order or fields.Datetime.now()
            cost, is_fallback = line.product_id._get_replacement_cost_for(
                company,
                line.product_uom_id or line.product_id.uom_id,
                line.currency_id or company.currency_id,
                fields.Date.to_date(date),
            )
            line.replacement_cost_unit = cost
            line.replacement_cost_fallback = is_fallback

    @api.depends('price_subtotal', 'product_uom_qty', 'replacement_cost_unit')
    def _compute_replacement_margin(self) -> None:
        for line in self:
            line.replacement_margin = (
                line.price_subtotal - line.replacement_cost_unit * line.product_uom_qty
            )
            line.replacement_margin_percent = (
                line.price_subtotal and line.replacement_margin / line.price_subtotal
            )

    def _refresh_replacement_cost(self) -> None:
        """Fuerza el recálculo del costo de reposición (y del margen que depende
        de él) con los datos de hoy."""
        fields_to_compute = [
            self._fields['replacement_cost_unit'],
            self._fields['replacement_cost_fallback'],
        ]
        for field in fields_to_compute:
            self.env.add_to_compute(field, self)
        self.flush_recordset(['replacement_cost_unit', 'replacement_cost_fallback'])
