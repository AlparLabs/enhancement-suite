from __future__ import annotations

from odoo import api, fields, models


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    shelf_pricelist_warning = fields.Char(compute='_compute_shelf_pricelist_warning')

    @api.depends('pricelist_id', 'print_format')
    def _compute_shelf_pricelist_warning(self) -> None:
        shelf = self.env.company.shelf_pricelist_id
        for wizard in self:
            if wizard.print_format == '3x8xprice' and wizard.pricelist_id != shelf:
                wizard.shelf_pricelist_warning = (
                    f'La lista elegida no es la lista de góndola '
                    f'({shelf.display_name or "precio de venta"}): los productos '
                    f'seguirán como etiqueta pendiente.'
                )
            else:
                wizard.shelf_pricelist_warning = False

    def process(self):
        action = super().process()
        if self.print_format == '3x8xprice':
            templates = self.product_tmpl_ids or self.product_ids.product_tmpl_id
            self.env['product.price.watch'].sudo()._mark_printed(
                templates, self.env.company, self.pricelist_id,
            )
        return action
