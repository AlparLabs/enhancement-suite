from __future__ import annotations

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    shelf_pricelist_id = fields.Many2one(
        'product.pricelist', string='Lista de góndola',
        help='Lista con la que se imprimen las etiquetas de góndola. Vacía: precio de venta.',
    )
    markup_tolerance_pct = fields.Float(
        string='Tolerancia de recargo (puntos)', default=2.0,
        help='Se alerta cuando el recargo actual queda por debajo del objetivo menos esta tolerancia.',
    )
