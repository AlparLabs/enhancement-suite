# -*- coding: utf-8 -*-
from odoo import models, fields, api


class QueueTicketType(models.Model):
    _name = "queue.ticket.type"
    _description = "Tipo de Turno"
    _order = "sequence, id"

    name = fields.Char(string="Nombre", required=True, translate=True)
    code = fields.Char(
        string="Código",
        required=True,
        index=True,
        help="Identificador slug único para la API y la terminal (ej: caja, ventas, pickup)",
    )
    prefix = fields.Char(
        string="Prefijo",
        size=5,
        required=True,
        default="T",
        help="Letra o prefijo visible en el ticket impreso o digital (ej: C, V, R)",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    icon = fields.Char(
        string="Ícono",
        default="fa-ticket",
        help="Nombre de clase FontAwesome o ícono para la terminal (ej: fa-shopping-cart, fa-briefcase)",
    )
    color = fields.Char(
        string="Color Hex",
        default="#3498db",
        help="Color distintivo para botones de terminal y columnas de TV (ej: #e67e22)",
    )
    description = fields.Text(
        string="Descripción",
        help="Texto descriptivo o subtítulo que se muestra en el Kiosco para guiar al cliente",
    )
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "El código de tipo de turno debe ser único por compañía."),
    ]
