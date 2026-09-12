# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WebsiteB2BOrderSchedule(models.Model):
    _name = 'website.b2b.order.schedule'
    _description = 'Franja Horaria de Pedidos B2B'
    _order = 'day_of_week, hour_from'

    website_id = fields.Many2one(
        'website',
        string="Sitio Web",
        required=True,
        ondelete='cascade',
        index=True
    )
    day_of_week = fields.Selection([
        ('0', 'Lunes'),
        ('1', 'Martes'),
        ('2', 'Miércoles'),
        ('3', 'Jueves'),
        ('4', 'Viernes'),
        ('5', 'Sábado'),
        ('6', 'Domingo'),
    ], string="Día de la Semana", required=True, default='0')

    hour_from = fields.Float(
        string="Hora Desde",
        default=8.0,
        required=True,
        help="Hora de inicio de recepción de pedidos en formato 24hs (ej. 8.0 = 08:00)"
    )
    hour_to = fields.Float(
        string="Hora Hasta",
        default=18.0,
        required=True,
        help="Hora de corte de recepción de pedidos en formato 24hs (ej. 13.0 = 13:00, 18.0 = 18:00)"
    )

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for record in self:
            if record.hour_from < 0.0 or record.hour_from > 24.0 or record.hour_to < 0.0 or record.hour_to > 24.0:
                raise ValidationError(_("Las horas deben estar comprendidas entre las 00:00 y las 24:00."))
            if record.hour_from >= record.hour_to:
                raise ValidationError(_("La 'Hora Desde' debe ser menor que la 'Hora Hasta'."))
