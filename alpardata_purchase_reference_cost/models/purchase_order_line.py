from __future__ import annotations

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    reference_cost: float = fields.Float(
        string='Costo de referencia',
        compute='_compute_reference_cost',
        digits='Product Price',
        readonly=True,
        store=False,
        help=(
            'Costo de referencia comunicado por el proveedor cargado en esta '
            'orden. No es el costo del proveedor principal del producto: '
            'respeta el proveedor seleccionado en la orden.'
        ),
    )

    @api.depends(
        'product_id',
        'product_uom',
        'order_id.partner_id',
        'order_id.currency_id',
        'order_id.company_id',
        'company_id',
        'product_id.seller_ids.reference_cost',
        'product_id.seller_ids.company_id',
        'product_id.seller_ids.sequence',
        'product_id.seller_ids.date_start',
        'product_id.seller_ids.date_end',
        'product_id.seller_ids.currency_id',
        'product_id.seller_ids.product_uom',
        'product_id.uom_id',
        'product_id.uom_po_id',
    )
    def _compute_reference_cost(self) -> None:
        for line in self:
            line.reference_cost = line._get_order_vendor_reference_cost()

    def _get_order_vendor_reference_cost(self) -> float:
        """Costo de referencia del proveedor cargado en la orden.

        Resuelve el `product.supplierinfo` correspondiente al proveedor de la
        orden respetando la jerarquía de empresas de la línea (sucursal → matriz
        → global), reutilizando la misma lógica que el costo de referencia a
        nivel de producto. Convierte el costo a la unidad de medida (UoM) y a la
        moneda de la orden de compra. Si el proveedor no comunicó un costo de
        referencia —o la orden aún no tiene proveedor— devuelve 0.0.
        """
        self.ensure_one()
        partner = self.order_id.partner_id or self.partner_id
        company = self.company_id or self.order_id.company_id or self.env.company
        if not self.product_id or not partner or not company:
            return 0.0
        seller = self.product_id.product_tmpl_id.with_company(
            company
        )._get_reference_cost_seller(partner=partner)
        if not seller or seller.reference_cost <= 0:
            return 0.0

        ref_cost = seller.reference_cost
        seller_uom = seller.product_uom or self.product_id.uom_po_id or self.product_id.uom_id
        line_uom = self.product_uom or self.product_id.uom_po_id or self.product_id.uom_id
        if seller_uom and line_uom and seller_uom != line_uom:
            if seller_uom.category_id == line_uom.category_id:
                ref_cost = seller_uom._compute_price(ref_cost, line_uom)

        src_currency = seller.currency_id or company.currency_id
        dst_currency = self.order_id.currency_id or company.currency_id
        if src_currency and dst_currency and src_currency != dst_currency:
            date = self.order_id.date_order or fields.Date.context_today(self)
            ref_cost = src_currency._convert(
                ref_cost, dst_currency, company, date, round=False
            )
        return ref_cost

    def _compute_price_unit_and_date_planned_and_name(self):
        """Extiende el cálculo de precio del core.

        Cuando el proveedor de la orden tiene un costo de referencia (>0), se usa
        ese valor como precio unitario por defecto (editable). La orden de compra
        se emite con el costo de referencia del proveedor seleccionado; la factura
        final puede diferir. Si ese proveedor no tiene costo de referencia, se
        respeta el precio que calcula Odoo (precio de proveedor / último costo).
        Si el comprador ya piso el precio a mano, ese precio manda.
        """
        super()._compute_price_unit_and_date_planned_and_name()
        for line in self:
            if not line.product_id or line.invoice_lines:
                continue
            # Mismo criterio que el core en 19: si el comprador puso el precio a
            # mano (technical_price_unit quedo desfasado de price_unit) no se
            # pisa. El costo de referencia es un valor por defecto, no una
            # imposicion.
            if line.technical_price_unit != line.price_unit:
                continue
            ref_cost = line._get_order_vendor_reference_cost()
            if ref_cost <= 0:
                continue
            line._reset_reference_price_unit(ref_cost)

    def _reset_reference_price_unit(self, price_unit: float) -> None:
        """Fija `price_unit` manteniendo `technical_price_unit` en sincronía.

        Odoo 19 agrego `technical_price_unit` (no existe en 18) y lo usa como
        marca de "precio puesto a mano": mientras difiera de `price_unit`, el
        core corta al inicio de `_compute_price_unit_and_date_planned_and_name`
        y deja de recalcular precio, descripcion, fecha planificada y descuento
        de la linea. El costo de referencia es un valor por defecto calculado,
        no una edicion manual, asi que hay que escribir ambos campos —eso es lo
        que hace `_reset_price_unit()`, el unico camino soportado en 19 para
        fijar el precio de una linea.
        """
        self.ensure_one()
        self._reset_price_unit(price_unit)
