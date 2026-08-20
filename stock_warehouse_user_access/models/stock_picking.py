from odoo import api, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    _WAREHOUSE_TYPE_BY_CODE = {
        'incoming': 'in_type_id',
        'outgoing': 'out_type_id',
        'internal': 'int_type_id',
    }

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'picking_type_id' not in fields_list:
            return defaults
        if self.env.context.get('default_picking_type_id'):
            return defaults
        warehouse = self.env.user.default_warehouse_id
        if not warehouse:
            return defaults
        if warehouse.company_id.id != self.env.company.id:
            return defaults
        code = self.env.context.get('restricted_picking_type_code') or 'internal'
        field_name = self._WAREHOUSE_TYPE_BY_CODE.get(code)
        if not field_name:
            return defaults
        picking_type = warehouse[field_name]
        if picking_type:
            defaults['picking_type_id'] = picking_type.id
        return defaults
