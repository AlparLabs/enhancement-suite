import ast
import logging

from odoo import models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

# Acciones cuyo listado se acota a los almacenes del usuario, con las rutas a
# stock.warehouse que definen si un registro "le toca". Alcanza con una.
WAREHOUSE_FILTERED_ACTIONS = {
    'stock.stock_move_action': (
        'location_id.warehouse_id',
        'location_dest_id.warehouse_id',
        'picking_type_id.warehouse_id',
    ),
    'stock.stock_move_line_action': (
        'location_id.warehouse_id',
        'location_dest_id.warehouse_id',
        'move_id.picking_type_id.warehouse_id',
    ),
    'stock.action_stock_scrap': (
        'location_id.warehouse_id',
    ),
    'stock.action_orderpoint_replenish': (
        'warehouse_id',
    ),
}

# Acciones donde lo que se acota son las cantidades calculadas, no los
# registros: ver product.product._get_domain_locations.
WAREHOUSE_QTY_ACTIONS = (
    'stock.action_product_stock_view',
)

QTY_CONTEXT_KEY = 'warehouse_access_restrict_qty'


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        """Acota el dominio de las acciones de reportes al almacén del usuario.

        Es un filtro de interfaz: el dominio viaja con la acción y solo se
        aplica a lo que el cliente web lista. Los procesos del core (reservas,
        reabastecimiento, validaciones) siguen viendo todos los registros.
        """
        result = super()._get_action_dict()
        xml_id = result.get('xml_id')
        if xml_id in WAREHOUSE_FILTERED_ACTIONS:
            domain = self.env.user._get_warehouse_view_domain(
                WAREHOUSE_FILTERED_ACTIONS[xml_id]
            )
            if domain is not None:
                self._add_warehouse_domain(result, domain)
        elif xml_id in WAREHOUSE_QTY_ACTIONS:
            if self.env.user._get_restricted_warehouses() is not None:
                self._add_qty_context_key(result)
        return result

    def _add_warehouse_domain(self, action, domain):
        original = action.get('domain')
        if isinstance(original, str):
            try:
                original = ast.literal_eval(original)
            except (ValueError, SyntaxError):
                # Dominio dinámico (usa uid, context...): no se puede combinar
                # del lado servidor sin evaluarlo. Hoy ninguna acción de la
                # lista lo tiene; si alguna lo suma, avisar en vez de pisarlo.
                _logger.warning(
                    "No se pudo acotar por almacén la acción %s: dominio dinámico.",
                    action.get('xml_id'),
                )
                return
        # Se devuelve como string, igual que lo trae read(): hay llamadores del
        # core que hacen literal_eval(action['domain']).
        action['domain'] = repr(list(Domain.AND([original or [], domain])))

    def _add_qty_context_key(self, action):
        context = action.get('context') or '{}'
        if isinstance(context, str):
            try:
                context = ast.literal_eval(context)
            except (ValueError, SyntaxError):
                _logger.warning(
                    "No se pudo acotar por almacén la acción %s: contexto dinámico.",
                    action.get('xml_id'),
                )
                return
        action['context'] = repr({**context, QTY_CONTEXT_KEY: True})
