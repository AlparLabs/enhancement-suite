from odoo import models


class StockForecastedProductProduct(models.AbstractModel):
    _inherit = 'stock.forecasted_product_product'

    def _get_report_data(self, product_template_ids=False, product_ids=False):
        res = super()._get_report_data(
            product_template_ids=product_template_ids, product_ids=product_ids)
        warehouse = self._get_warehouse()
        res['lots'] = self._get_lots_data(product_template_ids, product_ids, warehouse)
        return res

    def _get_lot_tracked_products(self, product_template_ids, product_ids):
        if product_template_ids:
            products = self.env['product.product'].search([
                ('product_tmpl_id', 'in', product_template_ids),
            ])
        else:
            products = self.env['product.product'].browse(product_ids)
        return products.filtered(lambda p: p.tracking == 'lot')

    def _get_lots_data(self, product_template_ids, product_ids, warehouse):
        products = self._get_lot_tracked_products(product_template_ids, product_ids)
        if not products:
            return []

        quants = self.env['stock.quant'].search([
            ('product_id', 'in', products.ids),
            ('lot_id', '!=', False),
            ('location_id', 'child_of', warehouse.view_location_id.id),
            ('location_id.usage', '=', 'internal'),
        ])

        lots_by_id = {}
        for quant in quants:
            entry = lots_by_id.setdefault(quant.lot_id.id, {
                'id': quant.lot_id.id,
                'display_name': quant.lot_id.display_name,
                'product_display_name': quant.product_id.display_name,
                'quantity': 0.0,
                'reserved_quantity': 0.0,
                'uom': quant.product_uom_id.name,
            })
            entry['quantity'] += quant.quantity
            entry['reserved_quantity'] += quant.reserved_quantity

        lots = []
        for entry in lots_by_id.values():
            entry['available_quantity'] = entry['quantity'] - entry['reserved_quantity']
            if entry['quantity'] or entry['available_quantity']:
                lots.append(entry)
        lots.sort(key=lambda lot: lot['available_quantity'])
        return lots
