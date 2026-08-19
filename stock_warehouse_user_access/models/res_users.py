from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    warehouse_access_ids = fields.Many2many(
        'stock.warehouse',
        'res_users_stock_warehouse_access_rel',
        'user_id',
        'warehouse_id',
        string='Almacenes permitidos',
        help="Almacenes cuyas transferencias y órdenes de compra puede ver el "
             "usuario. Si está vacío y el usuario no tiene el permiso 'Ver "
             "todos los almacenes', no ve ningún documento con almacén.",
    )
    default_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén por defecto',
        help="Almacén que se propone al crear una transferencia o una orden "
             "de compra. Debe estar dentro de los almacenes permitidos.",
    )

    @api.constrains('warehouse_access_ids', 'default_warehouse_id')
    def _check_default_warehouse_allowed(self):
        for user in self:
            if not user.default_warehouse_id:
                continue
            if user.default_warehouse_id not in user.warehouse_access_ids:
                raise ValidationError(_(
                    "El almacén por defecto de %(user)s debe estar dentro de "
                    "sus almacenes permitidos.",
                    user=user.name,
                ))
