from __future__ import annotations

import logging
from typing import Any

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductCostSchedule(models.Model):
    """
    Programación de cambios futuros de Costo de Referencia.

    Permite pre-cargar un cambio de costo con fecha de vigencia.
    El cron job diario aplica automáticamente los registros
    cuya fecha_vigencia <= hoy y estado == 'scheduled'.

    Flujo:
        borrador (draft) → programado (scheduled) → aplicado (done)
        cualquier estado → cancelado (cancelled)
    """
    _name = 'product.cost.schedule'
    _description = 'Programación de Costo de Referencia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'effective_date asc, id asc'
    _check_company_auto = True

    name: str = fields.Char(
        string='Descripción',
        required=True,
        tracking=True,
        default=lambda self: self._default_name(),
    )

    product_tmpl_id: models.Model = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
    )

    product_categ_id: models.Model = fields.Many2one(
        related='product_tmpl_id.categ_id',
        string='Categoría',
        store=True,
        readonly=True,
    )

    company_id: models.Model = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        index=True,
    )

    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
        readonly=True,
    )

    current_reference_cost: float = fields.Float(
        string='Costo referencia actual',
        digits='Product Price',
        compute='_compute_current_cost',
        store=False,
    )

    new_reference_cost: float = fields.Float(
        string='Nuevo costo de referencia',
        digits='Product Price',
        required=True,
        tracking=True,
        help='El costo de referencia que se aplicará en la fecha de vigencia.',
    )

    effective_date: fields.Date = fields.Date(
        string='Fecha de vigencia',
        required=True,
        tracking=True,
        help='A partir de esta fecha el nuevo costo de referencia estará activo.',
    )

    state: str = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('scheduled', 'Programado'),
            ('done', 'Aplicado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
        index=True,
    )

    applied_date: fields.Datetime = fields.Datetime(
        string='Fecha de aplicación real',
        readonly=True,
        copy=False,
    )

    applied_by: models.Model = fields.Many2one(
        'res.users',
        string='Aplicado por',
        readonly=True,
        copy=False,
    )

    notes: str = fields.Text(
        string='Justificación / Notas',
        help='Motivo del cambio de costo (ej: nuevo acuerdo con proveedor, ajuste por inflación).',
    )

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('product_tmpl_id', 'product_tmpl_id.reference_cost')
    def _compute_current_cost(self) -> None:
        for rec in self:
            rec.current_reference_cost = rec.product_tmpl_id.reference_cost

    def _default_name(self) -> str:
        return f'Programación de costo — {fields.Date.today()}'

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('new_reference_cost')
    def _check_new_cost(self) -> None:
        for rec in self:
            if rec.new_reference_cost < 0:
                raise ValidationError(
                    'El nuevo costo de referencia no puede ser negativo.'
                )

    @api.constrains('effective_date', 'product_tmpl_id', 'company_id', 'state')
    def _check_no_duplicate_scheduled(self) -> None:
        for rec in self:
            if rec.state not in ('scheduled',):
                continue
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('product_tmpl_id', '=', rec.product_tmpl_id.id),
                ('company_id', '=', rec.company_id.id),
                ('effective_date', '=', rec.effective_date),
                ('state', '=', 'scheduled'),
            ])
            if duplicate:
                raise ValidationError(
                    f'Ya existe una programación activa para el producto '
                    f'"{rec.product_tmpl_id.name}" en la fecha '
                    f'{rec.effective_date}. Cancelá la anterior antes de crear una nueva.'
                )

    # ── Acciones de botón ─────────────────────────────────────────────────────
    def action_schedule(self) -> None:
        """Confirma la programación y la deja lista para que el cron la aplique."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError('Solo se pueden programar registros en estado Borrador.')
        self.write({'state': 'scheduled'})
        self.message_post(
            body=f'Programación confirmada. Se aplicará el <b>{self.effective_date}</b>. '
                 f'Nuevo costo de referencia: <b>${self.new_reference_cost:,.2f}</b>.'
        )

    def action_cancel(self) -> None:
        """Cancela la programación."""
        for rec in self:
            if rec.state == 'done':
                raise ValidationError(
                    'No se puede cancelar una programación que ya fue aplicada.'
                )
        self.write({'state': 'cancelled'})

    def action_reset_draft(self) -> None:
        """Vuelve a borrador (solo desde cancelado)."""
        for rec in self:
            if rec.state != 'cancelled':
                raise ValidationError(
                    'Solo se puede resetear a borrador desde estado Cancelado.'
                )
        self.write({'state': 'draft'})

    def action_apply_now(self) -> None:
        """Aplica el costo manualmente (sin esperar el cron)."""
        self.ensure_one()
        if self.state not in ('draft', 'scheduled'):
            raise ValidationError('Solo se pueden aplicar programaciones en estado Borrador o Programado.')
        self._apply_cost_change()

    # ── Método de aplicación ─────────────────────────────────────────────────
    def _apply_cost_change(self) -> None:
        """
        Aplica el reference_cost creando un nuevo supplierinfo con
        date_start = effective_date para el proveedor principal del producto.
        El campo computed product.template.reference_cost se actualiza solo.
        """
        self.ensure_one()
        old_cost = self.product_tmpl_id.reference_cost
        reason = self.notes or f'Programación #{self.name}'

        primary_seller = self.product_tmpl_id.seller_ids.filtered(
            lambda s: not s.company_id or s.company_id == self.company_id
        ).sorted('sequence')

        if primary_seller:
            seller = primary_seller[0]
            self.env['product.supplierinfo'].sudo().with_context(
                _change_reason=reason,
            ).create({
                'partner_id': seller.partner_id.id,
                'product_tmpl_id': self.product_tmpl_id.id,
                'company_id': self.company_id.id,
                'reference_cost': self.new_reference_cost,
                'price': seller.price,
                'date_start': self.effective_date,
                'sequence': seller.sequence,
            })
        else:
            _logger.warning(
                'ProductCostSchedule #%s: producto %s no tiene proveedor principal. '
                'No se puede aplicar el costo de referencia.',
                self.id, self.product_tmpl_id.name,
            )

        self.write({
            'state': 'done',
            'applied_date': fields.Datetime.now(),
            'applied_by': self.env.uid,
        })

        self.message_post(
            body=(
                f'✅ Costo de referencia actualizado. '
                f'Anterior: <b>${old_cost:,.2f}</b> → '
                f'Nuevo: <b>${self.new_reference_cost:,.2f}</b>.'
            )
        )
        _logger.info(
            'ProductCostSchedule #%s aplicado. Producto: %s | '
            'Costo anterior: %.2f | Nuevo costo: %.2f',
            self.id, self.product_tmpl_id.name, old_cost, self.new_reference_cost,
        )

    # ── Cron ─────────────────────────────────────────────────────────────────
    @api.model
    def _cron_apply_scheduled_costs(self) -> None:
        """
        Cron job diario.
        Aplica todas las programaciones con effective_date <= hoy y state = 'scheduled'.
        """
        today = fields.Date.today()
        scheduled = self.search([
            ('state', '=', 'scheduled'),
            ('effective_date', '<=', today),
        ])

        _logger.info(
            'Cron de costos de referencia: procesando %d programaciones.', len(scheduled)
        )

        for schedule in scheduled:
            try:
                schedule._apply_cost_change()
            except Exception as e:
                _logger.error(
                    'Error al aplicar programación #%s para producto %s: %s',
                    schedule.id, schedule.product_tmpl_id.name, str(e)
                )
                continue

        # Recalcula los productos cuyos supplierinfo cruzaron una fecha de
        # vigencia: reference_cost es store=True pero depende de la fecha de hoy,
        # así que el paso del tiempo por sí solo no dispara el recálculo.
        self.env['product.template']._cron_recompute_reference_cost()

        _logger.info('Cron de costos de referencia: finalizado.')
