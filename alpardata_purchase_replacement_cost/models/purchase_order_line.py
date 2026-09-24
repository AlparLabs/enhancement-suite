from __future__ import annotations

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount_cascade = fields.Char(
        string='Bonificaciones',
        readonly=True,
        copy=True,
        help='Bonificaciones en cascada negociadas con el proveedor al cargar la '
             'línea. El % de descuento de la línea es su equivalente.',
    )

    @api.model
    def _get_cascade_seller(self, product, company, partner):
        """Ficha del proveedor de la orden, con la misma jerarquía de empresas
        que el costo de referencia."""
        if not product or not company or not partner:
            return self.env['product.supplierinfo']
        return product.product_tmpl_id.with_company(company)._get_reference_cost_seller(
            partner=partner,
        )

    def _apply_discount_cascade(self) -> None:
        """Pone el descuento equivalente de la cascada del proveedor.

        No toca líneas con precio puesto a mano ni líneas facturadas. Sin
        cascada deja el descuento que calculó el core (`supplierinfo.discount`).
        """
        for line in self:
            if not line.product_id or line.invoice_lines or not line.company_id:
                continue
            if line.technical_price_unit != line.price_unit:
                continue
            seller = self._get_cascade_seller(
                line.product_id, line.company_id,
                line.order_id.partner_id or line.partner_id,
            )
            cascade = seller.effective_discount_cascade if seller else False
            if cascade:
                line.discount = seller.discount_equivalent_pct
                line.discount_cascade = cascade
            else:
                line.discount_cascade = False

    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()
        self._apply_discount_cascade()

    @api.model
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom,
                                     company_id, partner_id, po):
        vals = super()._prepare_purchase_order_line(
            product_id, product_qty, product_uom, company_id, partner_id, po,
        )
        seller = self._get_cascade_seller(product_id, company_id, partner_id)
        if seller and seller.effective_discount_cascade:
            vals['discount'] = seller.discount_equivalent_pct
            vals['discount_cascade'] = seller.effective_discount_cascade
        return vals
