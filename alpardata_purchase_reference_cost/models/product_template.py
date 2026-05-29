import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ── Costo de referencia comercial ────────────────────────────────────────
    reference_cost = fields.Float(
        string='Costo de referencia',
        digits='Product Price',
        default=0.0,
        company_dependent=True,
        help=(
            'Costo comercial estable utilizado para calcular márgenes, '
            'listas de precios y BOM. '
            'NO se modifica automáticamente con recepciones de mercadería '
            'ni facturas de proveedor (a diferencia del Precio de Coste '
            'que usa AVCO/FIFO). '
            'Usá este campo como base para el precio de venta y el margen. '
            'Actualizalo manualmente o via programación de costos.'
        ),
    )

    reference_cost_last_update = fields.Datetime(
        string='Última actualización del costo de referencia',
        readonly=True,
        copy=False,
        help='Fecha y hora de la última vez que se modificó el reference_cost.',
    )

    reference_cost_updated_by = fields.Many2one(
        'res.users',
        string='Actualizado por',
        readonly=True,
        copy=False,
    )

    # ── Indicador de divergencia vs AVCO ─────────────────────────────────────
    cost_divergence_pct = fields.Float(
        string='Divergencia AVCO vs Referencia (%)',
        compute='_compute_cost_divergence',
        store=False,
        help=(
            'Diferencia porcentual entre el Precio de Coste (AVCO) y el '
            'Costo de Referencia. Si supera el umbral configurado en '
            'Ajustes, aparece un indicador visual de alerta.'
        ),
    )

    cost_divergence_alert = fields.Selection(
        selection=[
            ('ok', 'OK'),
            ('warning', 'Atención'),
            ('critical', 'Crítico'),
        ],
        string='Estado de divergencia',
        compute='_compute_cost_divergence',
        store=False,
    )

    # ── Programaciones pendientes ─────────────────────────────────────────────
    cost_schedule_count = fields.Integer(
        string='Programaciones pendientes',
        compute='_compute_cost_schedule_count',
    )

    cost_history_count = fields.Integer(
        string='Historial de cambios',
        compute='_compute_cost_history_count',
    )

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('standard_price', 'reference_cost')
    def _compute_cost_divergence(self):
        threshold_warning = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'alpardata_purchase_reference_cost.divergence_threshold_warning', 10.0
            )
        )
        threshold_critical = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'alpardata_purchase_reference_cost.divergence_threshold_critical', 25.0
            )
        )

        for rec in self:
            if not rec.reference_cost or rec.reference_cost == 0.0:
                rec.cost_divergence_pct = 0.0
                rec.cost_divergence_alert = 'ok'
                continue

            divergence = abs(
                (rec.standard_price - rec.reference_cost) / rec.reference_cost * 100
            )
            rec.cost_divergence_pct = divergence

            if divergence >= threshold_critical:
                rec.cost_divergence_alert = 'critical'
            elif divergence >= threshold_warning:
                rec.cost_divergence_alert = 'warning'
            else:
                rec.cost_divergence_alert = 'ok'

    def _compute_cost_schedule_count(self) -> None:
        for rec in self:
            rec.cost_schedule_count = self.env['product.cost.schedule'].search_count([
                ('product_tmpl_id', '=', rec.id),
                ('state', 'in', ('pending', 'scheduled')),
            ])

    def _compute_cost_history_count(self) -> None:
        for rec in self:
            rec.cost_history_count = self.env['product.cost.history'].search_count([
                ('product_tmpl_id', '=', rec.id),
            ])

    # ── Override write para loguear cambios ───────────────────────────────────
    def write(self, vals: dict) -> bool:
        # Si se modifica reference_cost, registrar auditoría
        if 'reference_cost' in vals:
            for rec in self:
                old_cost = rec.reference_cost
                new_cost = vals['reference_cost']
                if old_cost != new_cost:
                    self.env['product.cost.history'].sudo().create({
                        'product_tmpl_id': rec.id,
                        'old_reference_cost': old_cost,
                        'new_reference_cost': new_cost,
                        'change_date': fields.Datetime.now(),
                        'changed_by': self.env.uid,
                        'change_reason': (
                            self.env.context.get('_change_reason')
                            or vals.get('_change_reason')
                            or 'Actualización manual'
                        ),
                        'company_id': self.env.company.id,
                    })

            vals['reference_cost_last_update'] = fields.Datetime.now()
            vals['reference_cost_updated_by'] = self.env.uid

        return super().write(vals)

    # ── Acciones de smart buttons ─────────────────────────────────────────────
    def action_view_cost_schedules(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Programaciones de costo',
            'res_model': 'product.cost.schedule',
            'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }

    def action_view_cost_history(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Historial de costo de referencia',
            'res_model': 'product.cost.history',
            'view_mode': 'list',
            'domain': [('product_tmpl_id', '=', self.id)],
        }
