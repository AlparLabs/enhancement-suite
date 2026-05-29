from __future__ import annotations

from odoo import api, fields, models


class ProductCostHistory(models.Model):
    """
    Historial inmutable de cambios del Costo de Referencia.

    Se genera automáticamente cada vez que product.template.reference_cost
    es modificado (via write override o via cron de product.cost.schedule).
    No es editable por el usuario.
    """
    _name = 'product.cost.history'
    _description = 'Historial de Cambios — Costo de Referencia'
    _order = 'change_date desc, id desc'
    _rec_name = 'product_tmpl_id'
    _check_company_auto = True

    product_tmpl_id: models.Model = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
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
        readonly=True,
    )

    old_reference_cost: float = fields.Float(
        string='Costo anterior',
        digits='Product Price',
        readonly=True,
    )

    new_reference_cost: float = fields.Float(
        string='Nuevo costo',
        digits='Product Price',
        readonly=True,
    )

    variation_pct: float = fields.Float(
        string='Variación (%)',
        compute='_compute_variation',
        store=True,
        readonly=True,
    )

    change_date: fields.Datetime = fields.Datetime(
        string='Fecha de cambio',
        required=True,
        readonly=True,
        index=True,
    )

    changed_by: models.Model = fields.Many2one(
        'res.users',
        string='Modificado por',
        readonly=True,
    )

    change_reason: str = fields.Char(
        string='Motivo',
        readonly=True,
    )

    @api.depends('old_reference_cost', 'new_reference_cost')
    def _compute_variation(self) -> None:
        for rec in self:
            if rec.old_reference_cost and rec.old_reference_cost != 0.0:
                rec.variation_pct = (
                    (rec.new_reference_cost - rec.old_reference_cost)
                    / rec.old_reference_cost * 100
                )
            else:
                rec.variation_pct = 0.0
