from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProductReferenceCostMassUpdate(models.TransientModel):
    """
    Wizard de actualización masiva de Costo de Referencia.

    Permite:
    - Actualizar inmediatamente (hoy) el reference_cost
      de todos los productos de una categoría o proveedor.
    - O programar el cambio para una fecha futura (crea product.cost.schedule).

    Modos de actualización:
    - 'fixed'   → Nuevo costo fijo para todos los seleccionados.
    - 'pct_inc' → Incremento porcentual sobre el reference_cost actual.
    - 'pct_dec' → Reducción porcentual sobre el reference_cost actual.
    """
    _name = 'product.reference.cost.mass.update'
    _description = 'Actualización Masiva de Costo de Referencia'

    update_mode = fields.Selection(
        selection=[
            ('immediate', 'Aplicar ahora'),
            ('scheduled', 'Programar para fecha futura'),
        ],
        string='Modo de aplicación',
        required=True,
        default='scheduled',
    )

    effective_date = fields.Date(
        string='Fecha de vigencia',
        default=fields.Date.today,
        help='Solo aplica si se elige "Programar para fecha futura".',
    )

    filter_type = fields.Selection(
        selection=[
            ('category', 'Por categoría de producto'),
            ('supplier', 'Por proveedor'),
            ('manual', 'Selección manual'),
        ],
        string='Filtrar por',
        required=True,
        default='category',
    )

    categ_id = fields.Many2one(
        'product.category',
        string='Categoría',
    )

    supplier_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        domain=[('supplier_rank', '>', 0)],
    )

    product_ids = fields.Many2many(
        'product.template',
        string='Productos (selección manual)',
    )

    value_mode = fields.Selection(
        selection=[
            ('fixed', 'Costo fijo'),
            ('pct_inc', 'Incremento porcentual (%)'),
            ('pct_dec', 'Reducción porcentual (%)'),
        ],
        string='Tipo de valor',
        required=True,
        default='fixed',
    )

    new_cost = fields.Float(
        string='Nuevo costo (ARS)',
        digits='Product Price',
    )

    percentage = fields.Float(
        string='Porcentaje (%)',
        digits=(5, 2),
    )

    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )

    notes = fields.Text(
        string='Justificación',
        help='Motivo del cambio masivo (aparece en historial de cada producto).',
    )

    # ── Preview ───────────────────────────────────────────────────────────────
    preview_count = fields.Integer(
        string='Productos afectados',
        compute='_compute_preview_count',
    )

    @api.depends('filter_type', 'categ_id', 'supplier_id', 'product_ids')
    def _compute_preview_count(self):
        for rec in self:
            rec.preview_count = len(rec._get_target_products())

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_target_products(self):
        """Devuelve los productos que serán afectados por el wizard."""
        self.ensure_one()
        domain = [('type', '!=', 'service')]

        if self.filter_type == 'category':
            if not self.categ_id:
                return self.env['product.template']
            domain.append(('categ_id', 'child_of', self.categ_id.id))
        elif self.filter_type == 'supplier':
            if not self.supplier_id:
                return self.env['product.template']
            products_via_supplierinfo = self.env['product.supplierinfo'].search([
                ('partner_id', '=', self.supplier_id.id),
            ]).mapped('product_tmpl_id')
            if not products_via_supplierinfo:
                return self.env['product.template']
            domain.append(('id', 'in', products_via_supplierinfo.ids))
        elif self.filter_type == 'manual':
            if not self.product_ids:
                return self.env['product.template']
            return self.product_ids

        return self.env['product.template'].search(domain)

    def _compute_new_cost_for_product(self, product):
        """Calcula el nuevo costo para un producto según el modo elegido."""
        if self.value_mode == 'fixed':
            return self.new_cost
        elif self.value_mode == 'pct_inc':
            return product.reference_cost * (1 + self.percentage / 100)
        elif self.value_mode == 'pct_dec':
            return product.reference_cost * (1 - self.percentage / 100)
        return product.reference_cost

    # ── Validaciones ─────────────────────────────────────────────────────────
    @api.constrains('value_mode', 'new_cost', 'percentage')
    def _check_values(self):
        for rec in self:
            if rec.value_mode == 'fixed' and rec.new_cost < 0:
                raise ValidationError('El nuevo costo fijo no puede ser negativo.')
            if rec.value_mode in ('pct_inc', 'pct_dec') and rec.percentage <= 0:
                raise ValidationError('El porcentaje debe ser mayor a 0.')
            if rec.value_mode == 'pct_dec' and rec.percentage >= 100:
                raise ValidationError('La reducción no puede ser del 100% o más.')

    @api.constrains('update_mode', 'effective_date')
    def _check_date(self):
        for rec in self:
            if rec.update_mode == 'scheduled' and not rec.effective_date:
                raise ValidationError(
                    'Debés indicar una fecha de vigencia para la programación.'
                )

    # ── Acción principal ─────────────────────────────────────────────────────
    def action_apply(self):
        self.ensure_one()
        products = self._get_target_products()

        if not products:
            raise UserError(
                'No se encontraron productos que cumplan los criterios seleccionados.'
            )

        reason = self.notes or 'Actualización masiva de costo de referencia'

        if self.update_mode == 'immediate':
            # Aplicar directamente
            for product in products:
                new_cost = self._compute_new_cost_for_product(product)
                product.with_context(
                    force_company=self.company_id.id,
                    _change_reason=reason,
                ).write({'reference_cost': new_cost})

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Actualización completada',
                    'message': f'Se actualizó el costo de referencia de {len(products)} producto(s).',
                    'type': 'success',
                    'sticky': False,
                },
            }

        elif self.update_mode == 'scheduled':
            # Crear programaciones
            schedules_created = 0
            for product in products:
                new_cost = self._compute_new_cost_for_product(product)
                # Verificar si ya existe una programación para ese día
                existing = self.env['product.cost.schedule'].search([
                    ('product_tmpl_id', '=', product.id),
                    ('company_id', '=', self.company_id.id),
                    ('effective_date', '=', self.effective_date),
                    ('state', '=', 'scheduled'),
                ])
                if existing:
                    # Actualizar el existente
                    existing.write({
                        'new_reference_cost': new_cost,
                        'notes': reason,
                    })
                else:
                    self.env['product.cost.schedule'].create({
                        'name': f'Actualiz. masiva — {product.name} — {self.effective_date}',
                        'product_tmpl_id': product.id,
                        'company_id': self.company_id.id,
                        'new_reference_cost': new_cost,
                        'effective_date': self.effective_date,
                        'state': 'scheduled',
                        'notes': reason,
                    })
                    schedules_created += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Programaciones creadas',
                    'message': (
                        f'Se crearon/actualizaron {schedules_created} programaciones '
                        f'para el {self.effective_date}.'
                    ),
                    'type': 'success',
                    'sticky': False,
                },
            }
