import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    reference_cost = fields.Float(
        string='Costo de referencia (proveedor)',
        digits='Product Price',
        default=0.0,
        help=(
            'Precio de lista o costo de referencia comunicado por este proveedor. '
            'Si este proveedor es el principal del producto (menor sequence), '
            'este valor se sincroniza automáticamente con el '
            'Costo de Referencia del producto.'
        ),
    )

    supplierinfo_cost_history_count = fields.Integer(
        string='Historial de precios',
        compute='_compute_history_count',
    )

    @api.depends_context('company')
    def _compute_history_count(self):
        for rec in self:
            rec.supplierinfo_cost_history_count = self.env[
                'product.supplierinfo.cost.history'
            ].search_count([('supplierinfo_id', '=', rec.id)])

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_primary_for_product(self) -> bool:
        """
        Returns True if this supplierinfo is the primary supplier for its product
        (lowest sequence, considering company scope).
        The primary supplier's reference_cost is synced to product.template.
        """
        self.ensure_one()
        company_id = (self.company_id or self.env.company).id
        primary = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            '|',
            ('company_id', '=', company_id),
            ('company_id', '=', False),
        ], order='sequence asc, id asc', limit=1)
        return primary.id == self.id

    # ── Write override: log history + sync to product ─────────────────────────

    def write(self, vals: dict) -> bool:
        if 'reference_cost' in vals:
            new_cost = vals['reference_cost']
            change_reason = self.env.context.get('_change_reason', 'Actualización manual')

            for rec in self:
                old_cost = rec.reference_cost
                if old_cost == new_cost:
                    continue

                self.env['product.supplierinfo.cost.history'].sudo().create({
                    'supplierinfo_id': rec.id,
                    'product_tmpl_id': rec.product_tmpl_id.id,
                    'partner_id': rec.partner_id.id,
                    'company_id': (rec.company_id or self.env.company).id,
                    'old_reference_cost': old_cost,
                    'new_reference_cost': new_cost,
                    'change_date': fields.Datetime.now(),
                    'changed_by': self.env.uid,
                    'change_reason': change_reason,
                })

                # Sync to product.template.reference_cost when this is the primary supplier
                if rec.product_tmpl_id and rec._is_primary_for_product():
                    company_id = (rec.company_id or self.env.company).id
                    reason = change_reason if change_reason != 'Actualización manual' else (
                        f'Sincronizado desde proveedor principal — {rec.partner_id.name}'
                    )
                    rec.product_tmpl_id.sudo().with_context(
                        force_company=company_id,
                        _change_reason=reason,
                    ).write({'reference_cost': new_cost})

        return super().write(vals)

    # ── Smart button action ────────────────────────────────────────────────────

    def action_view_supplierinfo_cost_history(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Historial de precios — {self.partner_id.name}',
            'res_model': 'product.supplierinfo.cost.history',
            'view_mode': 'list,form',
            'domain': [('supplierinfo_id', '=', self.id)],
        }
