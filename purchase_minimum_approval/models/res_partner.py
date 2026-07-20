# purchase_minimum_approval/models/res_partner.py
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    apply_purchase_minimum = fields.Boolean(
        string='Aplica mínimo de compra',
        help='Si está activo, las órdenes de compra a este proveedor por debajo '
             'del mínimo quedarán pendientes de aprobación.',
        tracking=True,
    )
    purchase_minimum_amount = fields.Monetary(
        string='Mínimo de compra',
        currency_field='currency_id',
        help='Monto mínimo (subtotal sin impuestos, en moneda de la compañía) '
             'requerido para confirmar una orden de compra a este proveedor.',
        tracking=True,
    )
