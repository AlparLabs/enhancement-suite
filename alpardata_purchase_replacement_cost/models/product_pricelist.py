from __future__ import annotations

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    base = fields.Selection(
        selection_add=[('replacement_cost', 'Costo de Reposición')],
        ondelete={'replacement_cost': 'set default'},
    )

    def _compute_base_price(self, product, quantity, uom, date, currency, **kwargs) -> float:
        if self.base != 'replacement_cost':
            return super()._compute_base_price(product, quantity, uom, date, currency, **kwargs)
        currency.ensure_one()
        cost = product.replacement_cost
        if not cost:
            _logger.debug(
                'Producto "%s" sin costo de reposición. Se usa el costo estándar '
                'para la lista de precios.', product.display_name,
            )
            cost = product.standard_price
        return self._convert_commercial_cost(product, cost, uom, date, currency)

    def _get_price_label_base_str(self) -> str:
        self.ensure_one()
        if self.base == 'replacement_cost':
            return _('costo de reposición')
        return super()._get_price_label_base_str()
