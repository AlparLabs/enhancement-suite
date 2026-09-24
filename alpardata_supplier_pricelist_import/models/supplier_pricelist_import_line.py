from __future__ import annotations

from odoo import fields, models


class SupplierPricelistImportLine(models.Model):
    _name = 'supplier.pricelist.import.line'
    _description = 'Línea de importación de lista de proveedor'
    _order = 'import_id, row_number, id'

    import_id = fields.Many2one(
        'supplier.pricelist.import', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='import_id.company_id', store=True)
    row_number = fields.Integer(string='Fila')
    code = fields.Char(string='Código')
    supplierinfo_id = fields.Many2one('product.supplierinfo', string='Ficha de proveedor')
    product_tmpl_id = fields.Many2one('product.template', string='Producto')
    old_list_price = fields.Float(string='Lista anterior', digits='Product Price')
    new_list_price = fields.Float(string='Lista nueva', digits='Product Price')
    variation_pct = fields.Float(string='Variación (%)', digits=(16, 2))
    old_cascade = fields.Char(string='Bonif. anterior')
    new_cascade = fields.Char(string='Bonif. nueva')
    old_replacement_cost = fields.Float(string='Reposición anterior', digits='Product Price')
    new_replacement_cost = fields.Float(string='Reposición nueva', digits='Product Price')
    status = fields.Selection(
        [
            ('change', 'Cambia'),
            ('unchanged', 'Sin cambio'),
            ('not_found', 'No encontrado'),
            ('error', 'Error'),
        ],
        string='Estado', required=True, index=True,
    )
    message = fields.Char(string='Mensaje')
    to_apply = fields.Boolean(string='Aplicar')
