from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    reference_cost = fields.Float(
        string='Costo de referencia',
        related='product_id.reference_cost',
        digits='Product Price',
        readonly=True,
        store=False,
    )

    def _compute_price_unit_and_date_planned_and_name(self):
        """Extiende el cálculo de precio del core (Odoo 18).

        Cuando el producto tiene un costo de referencia (>0) para la empresa de
        la orden, se usa ese valor como precio unitario por defecto (editable).
        La orden de compra se emite con el costo de referencia; la factura final
        puede diferir. Si no hay costo de referencia, se respeta el precio que
        calcula Odoo (precio de proveedor / último costo).
        """
        super()._compute_price_unit_and_date_planned_and_name()
        for line in self:
            if not line.product_id or line.invoice_lines or not line.company_id:
                continue
            ref_cost = line.product_id.with_company(line.company_id).reference_cost
            if ref_cost <= 0:
                continue
            line.price_unit = line._reference_cost_in_order_currency(ref_cost)

    def _reference_cost_in_order_currency(self, ref_cost: float) -> float:
        """Convierte el costo de referencia (moneda de la empresa de la línea)
        a la moneda de la orden de compra."""
        self.ensure_one()
        src_currency = self.company_id.currency_id
        dst_currency = self.order_id.currency_id or src_currency
        if not src_currency or src_currency == dst_currency:
            return ref_cost
        date = self.order_id.date_order or fields.Date.context_today(self)
        return src_currency._convert(
            ref_cost, dst_currency, self.company_id, date, round=False
        )
