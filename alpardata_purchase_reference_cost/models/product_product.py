from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # El form de variantes (product_normal_form_view) hereda en modo primary
    # del form de product.template, por lo que el botón agregado allí también
    # se valida contra product.product: el método debe existir en ambos modelos.
    def action_view_cost_schedules(self) -> dict:
        self.ensure_one()
        return self.product_tmpl_id.action_view_cost_schedules()
