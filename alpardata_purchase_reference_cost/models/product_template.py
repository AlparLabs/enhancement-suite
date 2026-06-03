from __future__ import annotations

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ── Costo de referencia comercial ────────────────────────────────────────
    reference_cost: float = fields.Float(
        string='Costo de referencia',
        digits='Product Price',
        compute='_compute_reference_cost',
        store=True,
        help=(
            'Calculado automáticamente desde el Costo de Referencia del '
            'proveedor principal vigente (menor sequence, fecha válida hoy). '
            'Actualizalo cargando una nueva lista de precios del proveedor.'
        ),
    )

    # ── Indicador de divergencia vs AVCO ─────────────────────────────────────
    cost_divergence_pct: float = fields.Float(
        string='Divergencia AVCO vs Referencia (%)',
        compute='_compute_cost_divergence',
        store=False,
        help=(
            'Diferencia porcentual entre el Precio de Coste (AVCO) y el '
            'Costo de Referencia. Si supera el umbral configurado en '
            'Ajustes, aparece un indicador visual de alerta.'
        ),
    )

    cost_divergence_alert: str = fields.Selection(
        selection=[
            ('ok', 'OK'),
            ('warning', 'Atención'),
            ('critical', 'Crítico'),
        ],
        string='Estado de divergencia',
        compute='_compute_cost_divergence',
        store=False,
    )

    cost_schedule_count: int = fields.Integer(
        string='Programaciones pendientes',
        compute='_compute_cost_schedule_count',
    )

    cost_history_count: int = fields.Integer(
        string='Historial de precios por proveedor',
        compute='_compute_cost_history_count',
    )

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends(
        'seller_ids.reference_cost',
        'seller_ids.date_start',
        'seller_ids.date_end',
        'seller_ids.sequence',
        'seller_ids.company_id',
    )
    def _compute_reference_cost(self) -> None:
        today = fields.Date.today()
        company = self.env.company
        for tmpl in self:
            valid = tmpl.seller_ids.filtered(
                lambda s: s.reference_cost > 0
                and (not s.date_start or s.date_start <= today)
                and (not s.date_end or s.date_end >= today)
                and (not s.company_id or s.company_id == company)
            ).sorted('sequence')
            tmpl.reference_cost = valid[0].reference_cost if valid else 0.0

    @api.depends('standard_price', 'reference_cost')
    def _compute_cost_divergence(self) -> None:
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
            if not rec.reference_cost:
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

    @api.depends_context('company')
    def _compute_cost_schedule_count(self) -> None:
        for rec in self:
            rec.cost_schedule_count = self.env['product.cost.schedule'].search_count([
                ('product_tmpl_id', '=', rec.id),
                ('state', 'in', ('draft', 'scheduled')),
            ])

    @api.depends_context('company')
    def _compute_cost_history_count(self) -> None:
        for rec in self:
            rec.cost_history_count = self.env[
                'product.supplierinfo.cost.history'
            ].search_count([('product_tmpl_id', '=', rec.id)])

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
            'name': 'Historial de precios por proveedor',
            'res_model': 'product.supplierinfo.cost.history',
            'view_mode': 'list',
            'domain': [('product_tmpl_id', '=', self.id)],
        }
