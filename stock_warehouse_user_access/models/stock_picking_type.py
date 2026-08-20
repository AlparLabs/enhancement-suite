from odoo import api, models
from odoo.fields import Domain


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    @api.model
    def _get_user_warehouse_domain(self):
        """Dominio de tipos de operación visibles para el usuario actual.

        Devuelve una lista vacía cuando no corresponde filtrar: sin la clave de
        contexto, para usuarios eximidos, o para usuarios sin almacenes
        cargados (en ese caso el filtro real lo aplican las reglas de registro).
        """
        if not self.env.context.get('restrict_to_user_warehouses'):
            return []
        if self.env.user.has_group(
            'stock_warehouse_user_access.group_warehouse_access_all'
        ):
            return []
        warehouses = self.env.user.warehouse_access_ids
        if not warehouses:
            return []
        return [
            '|',
            ('warehouse_id', '=', False),
            ('warehouse_id', 'in', warehouses.ids),
        ]

    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        # **kwargs reenvia los argumentos keyword-only que _search sumo en 19
        # (active_test, bypass_access); omitirlos rompe a los llamadores del core.
        warehouse_domain = self._get_user_warehouse_domain()
        if warehouse_domain:
            domain = Domain.AND([domain, warehouse_domain])
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
