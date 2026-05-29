import logging
from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ProductPricelistItem(models.Model):
    """
    Extends product.pricelist.item to add 'reference_cost' as a valid
    base for formula-based pricelist rules.

    This allows retail companies to define sale prices as:
        sale_price = reference_cost + margin%
    instead of:
        sale_price = standard_price (AVCO) + margin%

    This is the key integration point: the commercial reference cost
    (stable, manually managed) drives the sale price instead of the
    AVCO cost (which fluctuates with every purchase receipt).
    """
    _inherit = 'product.pricelist.item'

    base = fields.Selection(
        selection_add=[('reference_cost', 'Costo de Referencia')],
        ondelete={'reference_cost': 'set default'},
    )

    def _compute_base_price(
        self,
        product,
        quantity: float,
        uom,
        date,
        currency,
    ) -> float:
        """
        Override to handle the 'reference_cost' base option.

        When base == 'reference_cost':
            - Reads product.template.reference_cost
            - Converts from company currency to the pricelist rule currency
            - Falls back to standard_price if reference_cost is 0.0

        For all other base values, delegates to the standard implementation.
        """
        if self.base != 'reference_cost':
            return super()._compute_base_price(product, quantity, uom, date, currency)

        currency.ensure_one()

        # Access reference_cost — works for both product.product and product.template
        # product.product inherits fields from product.template via _inherits
        ref_cost = product.reference_cost

        if not ref_cost:
            # Graceful fallback: if reference_cost is 0.0 (not yet set),
            # use standard_price to avoid selling at $0
            _logger.warning(
                'Product "%s" has no reference_cost set. '
                'Falling back to standard_price for pricelist calculation.',
                product.display_name,
            )
            ref_cost = product.standard_price

        # reference_cost is stored in the company currency
        src_currency = self.env.company.currency_id

        if src_currency != currency:
            ref_cost = src_currency._convert(
                ref_cost, currency, self.env.company, date, round=False
            )

        return ref_cost

    def _get_price_label_base_str(self) -> str:
        """
        Override to display the correct label for 'reference_cost' base
        in pricelist rule descriptions and reports.
        """
        self.ensure_one()
        if self.base == 'reference_cost':
            return _('costo de referencia')
        return super()._get_price_label_base_str()
