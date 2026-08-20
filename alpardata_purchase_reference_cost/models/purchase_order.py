from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        """Alta de líneas desde el catálogo (Odoo 18).

        El core, tras crear la línea, pisa `price_unit` con `seller.price`
        (purchase/models/purchase_order.py::_update_order_line_info), anulando el
        costo de referencia que aplica `_compute_price_unit_and_date_planned_and_name`.
        Volvemos a aplicar el costo de referencia del proveedor de la orden para
        que agregar desde el catálogo respete el mismo precio que el alta manual.
        """
        price = super()._update_order_line_info(product_id, quantity, **kwargs)
        line = self.order_line.filtered(
            lambda pol: pol.product_id.id == product_id
        )[:1]
        if not line or line.invoice_lines:
            return price
        ref_price = self._get_reference_cost_price(line.product_id)
        if ref_price <= 0:
            return price
        line.price_unit = ref_price
        return line.price_unit_discounted

    def _get_product_price_and_data(self, product):
        """Datos del producto para la tarjeta del catálogo (Odoo 18).

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
        matriz → global), igual que el costo de referencia a nivel de producto.
        """
        self.ensure_one()
        if not product or not self.partner_id:
            return 0.0
        company = self.company_id or self.env.company
        seller = product.product_tmpl_id.with_company(
            company
        )._get_reference_cost_seller(partner=self.partner_id)
        if not seller or seller.reference_cost <= 0:
            return 0.0
        ref_cost = seller.reference_cost
        src_currency = company.currency_id
        dst_currency = self.currency_id or src_currency
        if src_currency and dst_currency and src_currency != dst_currency:
            date = self.date_order or fields.Date.context_today(self)
            ref_cost = src_currency._convert(
                ref_cost, dst_currency, company, date, round=False
            )
        return ref_cost
