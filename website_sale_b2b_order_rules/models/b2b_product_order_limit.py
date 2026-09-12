# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class B2BProductOrderLimit(models.Model):
    _name = 'b2b.product.order.limit'
    _description = 'Límite de Compra B2B por Canal y Temporada'
    _order = 'website_id, date_from desc, week_number desc, id'

    name = fields.Char(
        string="Temporada / Nota",
        placeholder="ej. Permanente, Temporada Pascuas, Semana 28",
        help="Descripción o motivo de la regla de cupo (ej. Temporada Alta, Especial de Pascua, etc.)"
    )
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
    date_from = fields.Date(
        string="Fecha Desde",
        help="Fecha de inicio de vigencia de este cupo (opcional)."
    )
    date_to = fields.Date(
        string="Fecha Hasta",
        help="Fecha de finalización de vigencia de este cupo (opcional)."
    )
    week_number = fields.Integer(
        string="Semana del Año",
        default=0,
        help="Número de semana ISO (1 a 53). Si se define, el cupo rige exclusivamente en esa semana del año."
    )
    max_qty = fields.Float(
        string="Cantidad Máxima por Pedido",
        default=0.0,
        digits='Product Unit of Measure',
        help="Cantidad máxima que se puede encargar en un único pedido para este canal. Ingrese 0 para dejar sin límite."
    )
    min_qty = fields.Float(
        string="Cantidad Mínima por Pedido",
        default=0.0,
        digits='Product Unit of Measure',
        help="Cantidad mínima requerida si se encarga este producto. Ingrese 0 para no exigir mínimo."
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("La 'Fecha Desde' no puede ser posterior a la 'Fecha Hasta'."))

    @api.constrains('week_number')
    def _check_week_number(self):
        for record in self:
            if record.week_number and (record.week_number < 1 or record.week_number > 53):
                raise ValidationError(_("El número de semana debe estar entre 1 y 53."))
