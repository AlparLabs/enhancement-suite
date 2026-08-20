from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'picking_type_id' not in fields_list:
            return defaults
        if self.env.context.get('default_picking_type_id'):
            return defaults
        warehouse = self.env.user.default_warehouse_id
        if not warehouse or not warehouse.in_type_id:
            return defaults
        company_id = self.env.context.get('company_id') or self.env.company.id
        if warehouse.company_id.id != company_id:
            return defaults
        defaults['picking_type_id'] = warehouse.in_type_id.id
        return defaults
