from odoo import models
from odoo.fields import Domain

from .ir_actions import QTY_CONTEXT_KEY

# Marca interna: solo se acotan las ubicaciones mientras se calculan las
# cantidades del producto (campos no almacenados). La clave de la acción viaja
# en el contexto de todo lo que se dispara desde el reporte, y sin esta marca
# también alteraría cálculos almacenados, como los de los puntos de pedido.
_IN_QTY_COMPUTE = 'warehouse_access_in_qty_compute'


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _compute_quantities(self):
        if not self.env.context.get(QTY_CONTEXT_KEY):
            return super()._compute_quantities()
        return super(ProductProduct, self.with_context(**{
            _IN_QTY_COMPUTE: True,
        }))._compute_quantities()

    def _get_domain_locations(self):
        """Calcula las cantidades del reporte de Existencias solo sobre los
        almacenes del usuario.

        Si el usuario filtra por almacén, se respeta el filtro intersectado con
        sus almacenes; si filtra por ubicación, el core ya descarta las que no
        cuelgan de los almacenes que le pasamos.
        """
        context = self.env.context
        if not (context.get(QTY_CONTEXT_KEY) and context.get(_IN_QTY_COMPUTE)):
            return super()._get_domain_locations()
        allowed = self.env.user._get_restricted_warehouses()
        if allowed is None:
            return super()._get_domain_locations()

        warehouses = allowed
        requested = self._get_requested_warehouses()
        if requested is not None:
            warehouses &= requested
        if not warehouses:
            return (Domain.FALSE,) * 3
        return super(ProductProduct, self.with_context(
            warehouse_id=warehouses.ids,
            search_warehouse=False,
        ))._get_domain_locations()

    def _get_requested_warehouses(self):
        """Almacenes pedidos por contexto (ids o nombres), o None si no hay."""
        requested = (
            self.env.context.get('warehouse_id')
            or self.env.context.get('search_warehouse')
        )
        if not requested:
            return None
        if not isinstance(requested, list):
            requested = [requested]
        Warehouse = self.env['stock.warehouse']
        ids = [item for item in requested if isinstance(item, int)]
        names = [item for item in requested if not isinstance(item, int)]
        warehouses = Warehouse.browse(ids)
        if names:
            warehouses |= Warehouse.search(
                Domain.OR(Domain('name', 'ilike', name) for name in names)
            )
        return warehouses
