from __future__ import annotations

from odoo import fields, models


class SupplierPricelistImportProfile(models.Model):
    _name = 'supplier.pricelist.import.profile'
    _description = 'Perfil de importación de lista de proveedor'
    _order = 'partner_id, name'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )
    file_type = fields.Selection(
        [('xlsx', 'Excel (.xlsx)'), ('csv', 'CSV')],
        string='Tipo de archivo', required=True, default='xlsx',
    )
    sheet_name = fields.Char(string='Hoja', help='Vacío: primera hoja.')
    header_row = fields.Integer(string='Fila de encabezados', default=1, required=True)
    csv_delimiter = fields.Char(string='Separador CSV', size=1, default=';')
    csv_decimal = fields.Selection(
        [(',', 'Coma'), ('.', 'Punto')], string='Separador decimal', default=',', required=True,
    )
    csv_encoding = fields.Selection(
        [('utf-8', 'UTF-8'), ('latin-1', 'Latin-1 (Windows)')],
        string='Codificación CSV', default='utf-8',
    )
    match_by = fields.Selection(
        [
            ('supplier_code', 'Código del proveedor'),
            ('barcode', 'Código de barras'),
            ('default_code', 'Referencia interna'),
        ],
        string='Buscar producto por', required=True, default='supplier_code',
    )
    col_code = fields.Char(string='Columna código', required=True)
    col_price = fields.Char(string='Columna precio', required=True)
    col_cascade = fields.Char(string='Columna bonificaciones', help='Opcional.')
    price_includes_vat = fields.Boolean(string='El precio incluye IVA')
    vat_pct = fields.Float(string='IVA (%)', default=21.0)

    _header_row_positive = models.Constraint(
        'CHECK(header_row >= 1)', 'La fila de encabezados debe ser 1 o mayor.',
    )
