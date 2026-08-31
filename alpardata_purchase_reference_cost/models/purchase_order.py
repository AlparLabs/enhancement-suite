from __future__ import annotations

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _update_order_line_info(self, product_id, quantity, *, section_id=False, **kwargs):
        """Alta de líneas desde el catálogo.

        El core, tras crear la línea, pisa `price_unit` con `seller.price` via
        `_reset_price_unit()` (purchase/models/purchase_order.py), anulando el
        costo de referencia que aplica `_compute_price_unit_and_date_planned_and_name`.
        Volvemos a aplicar el costo de referencia del proveedor de la orden para
        que agregar desde el catálogo respete el mismo precio que el alta manual.

        `section_id` se declara explícitamente porque en 19 el core identifica la
        línea por (producto, sección): filtrar solo por producto y quedarse con
        la primera puede devolver una línea distinta de la que el core acaba de
        tocar cuando la orden tiene secciones, y entonces el costo de referencia
        se escribe en la línea equivocada.
        """
        price = super()._update_order_line_info(
            product_id, quantity, section_id=section_id, **kwargs
        )
        line = self.order_line.filtered(
            lambda pol: pol.product_id.id == product_id
            and pol.get_parent_section_line().id == section_id
        )[:1]
        if not line or line.invoice_lines:
            return price
        ref_price = self._get_reference_cost_price(line.product_id)
        if ref_price <= 0:
            return price
        line._reset_reference_price_unit(ref_price)
        return line.price_unit_discounted

    def _get_product_price_and_data(self, product):
        """Datos del producto para la tarjeta del catálogo.

        El core devuelve `seller.price_discounted` / `standard_price`. Cuando el
        proveedor de la orden tiene costo de referencia para el producto, lo
        mostramos en su lugar para que la vista previa del catálogo coincida con
        el precio que tomará la línea al agregarse.
        """
        product_infos = super()._get_product_price_and_data(product)
        ref_price = self._get_reference_cost_price(product)
        if ref_price > 0:
            product_infos['price'] = ref_price
        return product_infos

    def _get_reference_cost_price(self, product) -> float:
        """Costo de referencia del proveedor de la orden para `product`,
        convertido a la moneda de la orden. Devuelve 0.0 si no aplica.

        Resuelve el proveedor respetando la jerarquía de empresas (sucursal →
        matriz → global), igual que el costo de referencia a nivel de producto,
        y lo convierte a la unidad del producto: el catálogo crea la línea en
        esa unidad, aunque el proveedor cotice por bulto.
        """
        self.ensure_one()
        if not product or not self.partner_id:
            return 0.0
        company = self.company_id or self.env.company
        tmpl = product.product_tmpl_id.with_company(company)
        seller = tmpl._get_reference_cost_seller(partner=self.partner_id)
        ref_cost = tmpl._reference_cost_in_uom(seller)
        if ref_cost <= 0:
            return 0.0
        src_currency = company.currency_id
        dst_currency = self.currency_id or src_currency
        if src_currency and dst_currency and src_currency != dst_currency:
            date = self.date_order or fields.Date.context_today(self)
            ref_cost = src_currency._convert(
                ref_cost, dst_currency, company, date, round=False
            )
        return ref_cost
