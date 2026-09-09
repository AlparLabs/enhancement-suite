# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    b2b_order_limit_ids = fields.One2many(
        'b2b.product.order.limit',
        'product_tmpl_id',
        string="Límites B2B por Canal Web"
    )

    def _get_b2b_order_limit_for_website(self, website):
        """
        Retorna la regla b2b.product.order.limit aplicable para el sitio web indicado.
        """
        self.ensure_one()
        if not website:
            return self.env['b2b.product.order.limit']
        return self.b2b_order_limit_ids.filtered(lambda l: l.website_id == website)[:1]


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_b2b_order_limit_for_website(self, website):
        self.ensure_one()
        return self.product_tmpl_id._get_b2b_order_limit_for_website(website)

