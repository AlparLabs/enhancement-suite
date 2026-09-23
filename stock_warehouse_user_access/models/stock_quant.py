from odoo import api, models
from odoo.fields import Domain


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _restrict_action_to_user_warehouses(self, action):
        """Acota la acción a los quants de los almacenes del usuario.

        Filtro de interfaz: se aplica sobre el dominio de la acción que abre
        el listado, no sobre las búsquedas del core.
        """
        domain = self.env.user._get_warehouse_view_domain(
            ('location_id.warehouse_id',)
        )
        if domain is not None:
            action['domain'] = list(Domain.AND([action.get('domain') or [], domain]))
        return action

    @api.model
    def action_view_inventory(self):
        return self._restrict_action_to_user_warehouses(super().action_view_inventory())

    def _get_quants_action(self, extend=False):
        return self._restrict_action_to_user_warehouses(
            super()._get_quants_action(extend=extend)
        )
