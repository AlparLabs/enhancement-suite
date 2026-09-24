from __future__ import annotations

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class SupplierPricelistImport(models.Model):
    _name = 'supplier.pricelist.import'
    _description = 'Importación de lista de proveedor'
    _inherit = ['mail.thread']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    partner_id = fields.Many2one(
        'res.partner', string='Proveedor', required=True, tracking=True, index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )
    mode = fields.Selection(
        [('file', 'Archivo del proveedor'), ('percent', 'Aumento porcentual')],
        string='Modo', required=True, default='file',
    )
    profile_id = fields.Many2one(
        'supplier.pricelist.import.profile', string='Perfil',
        domain="[('partner_id', '=', partner_id)]", check_company=True,
    )
    file = fields.Binary(string='Archivo', attachment=True)
    file_name = fields.Char(string='Nombre del archivo')
    percent = fields.Float(string='Variación (%)', help='Negativo para bajas.')
    filter_categ_ids = fields.Many2many(
        'product.category', string='Categorías', help='Incluye subcategorías.',
    )
    filter_tag_ids = fields.Many2many('product.tag', string='Etiquetas')
    effective_date = fields.Date(
        string='Vigente desde', required=True, default=fields.Date.context_today, tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('preview', 'Vista previa'),
            ('done', 'Aplicada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado', default='draft', required=True, tracking=True, copy=False,
    )
    line_ids = fields.One2many('supplier.pricelist.import.line', 'import_id', string='Líneas')
    applied_date = fields.Datetime(string='Aplicada el', readonly=True, copy=False)
    applied_by = fields.Many2one('res.users', string='Aplicada por', readonly=True, copy=False)
    count_change = fields.Integer(compute='_compute_counts', string='Cambian')
    count_unchanged = fields.Integer(compute='_compute_counts', string='Sin cambio')
    count_not_found = fields.Integer(compute='_compute_counts', string='No encontrados')
    count_error = fields.Integer(compute='_compute_counts', string='Errores')

    @api.depends('line_ids.status')
    def _compute_counts(self) -> None:
        for rec in self:
            statuses = rec.line_ids.mapped('status')
            rec.count_change = statuses.count('change')
            rec.count_unchanged = statuses.count('unchanged')
            rec.count_not_found = statuses.count('not_found')
            rec.count_error = statuses.count('error')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'supplier.pricelist.import'
                ) or '/'
        return super().create(vals_list)
