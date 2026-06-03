import logging
from datetime import timedelta

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

    # ── Create / Write: log history ───────────────────────────────────────────
    # product.template.reference_cost es un campo computed que depende de
    # seller_ids, por lo que se recalcula automáticamente cuando se crea o
    # modifica cualquier supplierinfo. Solo necesitamos loguear el historial.

    def _log_reference_cost_history(self, old_cost: float, new_cost: float) -> None:
        if old_cost == new_cost:
            return
        self.env['product.supplierinfo.cost.history'].sudo().create({
            'supplierinfo_id': self.id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'partner_id': self.partner_id.id,
            'company_id': (self.company_id or self.env.company).id,
            'old_reference_cost': old_cost,
            'new_reference_cost': new_cost,
            'change_date': fields.Datetime.now(),
            'changed_by': self.env.uid,
            'change_reason': self.env.context.get('_change_reason', 'Actualización manual'),
        })

    def _close_previous_records(self) -> None:
        """
        Cierra los registros anteriores del mismo (partner, product_tmpl, company)
        que sigan vigentes a partir de self.date_start, poniéndoles
        date_end = date_start - 1 día.

        Garantiza que el nuevo registro sea el único vigente desde su fecha de
        inicio, independientemente del sequence.
        Solo aplica cuando el nuevo registro tiene date_start definido.
        """
        self.ensure_one()
        if not self.date_start:
            return

        company_id = (self.company_id or self.env.company).id
        previous = self.env['product.supplierinfo'].search([
            ('id', '!=', self.id),
            ('partner_id', '=', self.partner_id.id),
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            '|', ('company_id', '=', company_id), ('company_id', '=', False),
            '|', ('date_end', '=', False), ('date_end', '>=', self.date_start),
        ])
        if previous:
            previous.write({'date_end': self.date_start - timedelta(days=1)})

    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.reference_cost:
                rec._log_reference_cost_history(0.0, rec.reference_cost)
            rec._close_previous_records()
        return records

    def write(self, vals: dict) -> bool:
        if 'reference_cost' in vals:
            new_cost = vals['reference_cost']
            for rec in self:
                rec._log_reference_cost_history(rec.reference_cost, new_cost)
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
