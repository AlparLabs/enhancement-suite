from odoo import api, fields, models


class ProductSupplierinfoCostHistory(models.Model):
    """
    Historial inmutable de cambios del Costo de Referencia por proveedor.

    Se genera automáticamente en product.supplierinfo.write() cada vez que
    reference_cost cambia. No es editable por el usuario.

    A diferencia de product.cost.history (que registra cambios en el costo
    comercial del producto), este modelo registra los cambios por proveedor,
    permitiendo comparar la evolución de precios entre distintos proveedores.
    """

    _name = 'product.supplierinfo.cost.history'
    _description = 'Historial de Precios de Referencia por Proveedor'
    _order = 'change_date desc, id desc'
    _rec_name = 'partner_id'
    _check_company_auto = True

    supplierinfo_id = fields.Many2one(
        'product.supplierinfo',
        string='Ficha de proveedor',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
    )

    product_categ_id = fields.Many2one(
        related='product_tmpl_id.categ_id',
        string='Categoría',
        store=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        ondelete='restrict',
        index=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        readonly=True,
    )

    old_reference_cost = fields.Float(
        string='Precio anterior',
        digits='Product Price',
        readonly=True,
    )

    new_reference_cost = fields.Float(
        string='Nuevo precio',
        digits='Product Price',
        readonly=True,
    )

    variation_pct = fields.Float(
        string='Variación (%)',
        compute='_compute_variation',
        store=True,
        readonly=True,
    )

    change_date = fields.Datetime(
        string='Fecha de cambio',
        required=True,
        readonly=True,
        index=True,
    )

    changed_by = fields.Many2one(
        'res.users',
        string='Modificado por',
        readonly=True,
    )

    change_reason = fields.Char(
        string='Motivo',
        readonly=True,
    )

    @api.depends('old_reference_cost', 'new_reference_cost')
    def _compute_variation(self) -> None:
        for rec in self:
            if rec.old_reference_cost:
                rec.variation_pct = (
                    (rec.new_reference_cost - rec.old_reference_cost)
                    / rec.old_reference_cost * 100
                )
            else:
                rec.variation_pct = 0.0
