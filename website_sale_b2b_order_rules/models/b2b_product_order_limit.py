# -*- coding: utf-8 -*-
from odoo import fields, models


class B2BProductOrderLimit(models.Model):
    _name = 'b2b.product.order.limit'
    _description = 'Límite de Compra B2B por Canal Web'
    _order = 'website_id, product_tmpl_id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string="Plantilla de Producto",
        required=True,
        ondelete='cascade',
        index=True
    )
    website_id = fields.Many2one(
        'website',
        string="Canal / Sitio Web",
        required=True,
        ondelete='cascade',
        index=True
    )
    max_qty = fields.Float(
        string="Cantidad Máxima por Pedido",
        default=0.0,
        digits='Product Unit of Measure',
        help="Cantidad máxima de unidades que se pueden encargar en un único pedido para este canal. Ingrese 0 para dejar sin límite."
    )
    min_qty = fields.Float(
        string="Cantidad Mínima por Pedido",
        default=0.0,
        digits='Product Unit of Measure',
        help="Cantidad mínima de unidades requeridas si se encarga este producto. Ingrese 0 para no exigir mínimo."
    )

    _sql_constraints = [
        ('uniq_product_website', 'unique(product_tmpl_id, website_id)',
         'Ya existe una regla de límites para este producto en el canal web seleccionado.')
    ]
