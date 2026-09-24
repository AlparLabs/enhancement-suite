from __future__ import annotations

from odoo import api, fields, models

from ..tools import cascade_equivalent_pct, compute_replacement_cost, parse_discount_cascade
from .res_partner import check_cascade, check_pct_range

OWN_FIELDS = (
    'own_discount_cascade',
    'own_early_payment_pct',
    'own_freight_pct',
    'own_perception_pct',
)


def _fmt(amount: float) -> str:
    """1234.5 → '1.234,50' (formato argentino)."""
    return f'{amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _fmt_pct(value: float) -> str:
    return f'{value:g}'.replace('.', ',')


class ProductSupplierinfo(models.Model):
    _name = 'product.supplierinfo'
    _inherit = ['product.supplierinfo', 'commercial.conditions.access.mixin']

    _commercial_condition_fields = ('use_own_conditions',) + OWN_FIELDS

    use_own_conditions = fields.Boolean(
        string='Condiciones propias',
        help='Si está tildado, usa las condiciones cargadas acá en lugar de las '
             'del proveedor.',
    )
    own_discount_cascade = fields.Char(string='Bonificaciones (propias)')
    own_early_payment_pct = fields.Float(string='Pronto pago % (propio)')
    own_freight_pct = fields.Float(string='Flete % (propio)')
    own_perception_pct = fields.Float(string='Percepción % (propia)')

    effective_discount_cascade = fields.Char(
        string='Bonificaciones', compute='_compute_effective_conditions',
    )
    effective_early_payment_pct = fields.Float(
        string='Pronto pago (%)', compute='_compute_effective_conditions',
    )
    effective_freight_pct = fields.Float(
        string='Flete (%)', compute='_compute_effective_conditions',
    )
    effective_perception_pct = fields.Float(
        string='Percepción (%)', compute='_compute_effective_conditions',
    )
    # Sin `digits`: Float redondea el valor en caché a esa precisión y la
    # reposición se calcularía con 17,07 % en lugar de 17,065 % (10+5+3).
    discount_equivalent_pct = fields.Float(
        string='Bonificación equivalente (%)',
        compute='_compute_effective_conditions',
    )
    replacement_cost = fields.Float(
        string='Costo de reposición', digits='Product Price',
        compute='_compute_replacement_cost',
        help='Costo de referencia de este registro aplicando bonificaciones, pronto '
             'pago, flete, percepción e impuestos internos. En la unidad y moneda '
             'de esta ficha.',
    )
    replacement_cost_breakdown = fields.Char(
        string='Desglose', compute='_compute_replacement_cost',
    )

    @api.depends(
        'use_own_conditions', *OWN_FIELDS, 'company_id',
        'partner_id.commercial_partner_id.purchase_discount_cascade',
        'partner_id.commercial_partner_id.purchase_early_payment_pct',
        'partner_id.commercial_partner_id.purchase_freight_pct',
        'partner_id.commercial_partner_id.purchase_perception_pct',
    )
    @api.depends_context('company')
    def _compute_effective_conditions(self) -> None:
        for rec in self:
            if rec.use_own_conditions:
                cascade = rec.own_discount_cascade
                early = rec.own_early_payment_pct
                freight = rec.own_freight_pct
                perception = rec.own_perception_pct
            else:
                partner = rec.partner_id.commercial_partner_id.with_company(
                    rec.company_id or self.env.company
                )
                cascade = partner.purchase_discount_cascade
                early = partner.purchase_early_payment_pct
                freight = partner.purchase_freight_pct
                perception = partner.purchase_perception_pct
            rec.effective_discount_cascade = cascade or False
            rec.effective_early_payment_pct = early
            rec.effective_freight_pct = freight
            rec.effective_perception_pct = perception
            try:
                values = parse_discount_cascade(cascade)
            except ValueError:
                values = []
            rec.discount_equivalent_pct = cascade_equivalent_pct(values)

    @api.depends(
        'reference_cost', 'product_tmpl_id.internal_tax_pct',
        'discount_equivalent_pct', 'effective_early_payment_pct',
        'effective_freight_pct', 'effective_perception_pct',
    )
    @api.depends_context('company')
    def _compute_replacement_cost(self) -> None:
        for rec in self:
            internal = rec.product_tmpl_id.internal_tax_pct
            net, replacement = compute_replacement_cost(
                rec.reference_cost,
                rec.discount_equivalent_pct,
                rec.effective_early_payment_pct,
                rec.effective_freight_pct,
                rec.effective_perception_pct,
                internal,
            )
            rec.replacement_cost = replacement
            if not rec.reference_cost:
                rec.replacement_cost_breakdown = False
                continue
            extras = []
            if rec.effective_early_payment_pct:
                extras.append(f'−{_fmt_pct(rec.effective_early_payment_pct)}% PP')
            if rec.effective_freight_pct:
                extras.append(f'+{_fmt_pct(rec.effective_freight_pct)}% flete')
            if rec.effective_perception_pct:
                extras.append(f'+{_fmt_pct(rec.effective_perception_pct)}% percep.')
            if internal:
                extras.append(f'+{_fmt_pct(internal)}% internos')
            cascade = f' ({rec.effective_discount_cascade})' if rec.effective_discount_cascade else ''
            extras_txt = f' ({" ".join(extras)})' if extras else ''
            rec.replacement_cost_breakdown = (
                f'Lista {_fmt(rec.reference_cost)} → Neto {_fmt(net)}{cascade}'
                f' → Reposición {_fmt(replacement)}{extras_txt}'
            )

    @api.constrains('own_discount_cascade')
    def _check_own_discount_cascade(self) -> None:
        check_cascade(self, 'own_discount_cascade')

    @api.constrains('own_early_payment_pct', 'own_freight_pct', 'own_perception_pct')
    def _check_own_pcts(self) -> None:
        check_pct_range(self, OWN_FIELDS[1:], {
            'own_early_payment_pct': 'Pronto pago',
            'own_freight_pct': 'Flete',
            'own_perception_pct': 'Percepción no recuperable',
        })
