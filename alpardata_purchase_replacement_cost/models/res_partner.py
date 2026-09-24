from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import parse_discount_cascade

PARTNER_CONDITION_FIELDS = (
    'purchase_discount_cascade',
    'purchase_early_payment_pct',
    'purchase_freight_pct',
    'purchase_perception_pct',
)


def check_pct_range(records, field_names, label_by_field):
    """Valida 0 ≤ valor < 100 para porcentajes de condiciones comerciales."""
    for rec in records:
        for name in field_names:
            value = rec[name] or 0.0
            if not 0 <= value < 100:
                raise ValidationError(
                    f'{label_by_field[name]}: {value:g} fuera de rango '
                    '(debe ser mayor o igual a 0 y menor que 100).'
                )


def check_cascade(records, field_name):
    for rec in records:
        try:
            parse_discount_cascade(rec[field_name])
        except ValueError as err:
            raise ValidationError(str(err)) from err


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'commercial.conditions.access.mixin']

    _commercial_condition_fields = PARTNER_CONDITION_FIELDS

    purchase_discount_cascade = fields.Char(
        string='Bonificaciones',
        company_dependent=True,
        tracking=True,
        help='Bonificaciones en cascada del proveedor, p. ej. 10+5+3. '
             'Cada una se aplica sobre el neto de la anterior.',
    )
    purchase_early_payment_pct = fields.Float(
        string='Pronto pago (%)', company_dependent=True, tracking=True,
    )
    purchase_freight_pct = fields.Float(
        string='Flete (%)', company_dependent=True, tracking=True,
        help='Costo de flete/logística sobre el neto bonificado.',
    )
    purchase_perception_pct = fields.Float(
        string='Percepción no recuperable (%)', company_dependent=True, tracking=True,
        help='Percepciones (p. ej. IIBB) que no se recuperan, sobre el neto bonificado.',
    )

    @api.constrains('purchase_discount_cascade')
    def _check_purchase_discount_cascade(self) -> None:
        check_cascade(self, 'purchase_discount_cascade')

    @api.constrains('purchase_early_payment_pct', 'purchase_freight_pct',
                    'purchase_perception_pct')
    def _check_purchase_condition_pcts(self) -> None:
        check_pct_range(self, PARTNER_CONDITION_FIELDS[1:], {
            'purchase_early_payment_pct': 'Pronto pago',
            'purchase_freight_pct': 'Flete',
            'purchase_perception_pct': 'Percepción no recuperable',
        })
