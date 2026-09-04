# -*- coding: utf-8 -*-
from odoo import models, fields


class PosConfig(models.Model):
    _inherit = "pos.config"

    queue_type_id = fields.Many2one(
        "queue.ticket.type",
        string="Tipo de Turno Asignado",
        help="Cola de turnos que atiende prioritariamente este punto de venta",
    )
