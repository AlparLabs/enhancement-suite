from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


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

    def _get_restricted_warehouses(self):
        """Almacenes a los que se limita la vista del usuario.

        Devuelve None si el usuario no se filtra (permiso 'Ver todos los
        almacenes'). Un recordset vacío significa que se filtra y no ve nada.
        """
        self.ensure_one()
        if self.has_group('stock_warehouse_user_access.group_warehouse_access_all'):
            return None
        return self.warehouse_access_ids

    def _get_warehouse_view_domain(self, paths):
        """Dominio que deja solo lo que toca a los almacenes del usuario.

        `paths` son rutas a un campo stock.warehouse; alcanza con que una
        coincida. Devuelve None si el usuario no se filtra.
        """
        warehouses = self._get_restricted_warehouses()
        if warehouses is None:
            return None
        return Domain.OR(Domain(path, 'in', warehouses.ids) for path in paths)

    @api.model
    def _get_invalidation_fields(self):
        """Incluye los almacenes permitidos en la invalidación de caché.

        `ir.rule._compute_domain` cachea el dominio ya evaluado, con los ids de
        almacén adentro. Sin esto, quitarle un almacén a un usuario no surte
        efecto hasta que algo más limpie la caché del registro.
        """
        return super()._get_invalidation_fields() | {'warehouse_access_ids'}
