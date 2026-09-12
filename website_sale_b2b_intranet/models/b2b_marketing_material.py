# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _


class B2BMarketingMaterial(models.Model):
    _name = 'b2b.marketing.material'
    _description = 'Material de Marketing B2B / Intranet'
    _order = 'sequence, id desc'

    name = fields.Char(
        string='Título del Material',
        required=True,
        index=True,
    )
    category = fields.Selection([
        ('manual', 'Manuales y Protocolos de Operación'),
        ('promo', 'Material Gráfico y Promociones (Alta Resolución)'),
        ('pricing', 'Listas de Precios Sugeridos al Mostrador'),
        ('recipe', 'Recetas y Cafetería EntreDos'),
    ], string='Categoría', required=True, default='manual', index=True)

    website_ids = fields.Many2many(
        'website',
        'b2b_marketing_material_website_rel',
        'material_id',
        'website_id',
        string='Canales B2B Disponibles',
        help='Si se deja vacío, el material estará visible en todos los canales web de la compañía.',
    )
    file = fields.Binary(
        string='Archivo Adjunto',
        attachment=True,
        required=True,
    )
    file_name = fields.Char(
        string='Nombre del Archivo',
    )
    description = fields.Text(
        string='Instrucciones / Guía de Aplicación',
    )
    date_published = fields.Date(
        string='Fecha de Publicación',
        default=fields.Date.context_today,
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )
    download_count = fields.Integer(
        string='Descargas',
        default=0,
        readonly=True,
    )
    file_size_display = fields.Char(
        string='Tamaño',
        compute='_compute_file_details',
        store=True,
    )
    file_ext_display = fields.Char(
        string='Extensión',
        compute='_compute_file_details',
        store=True,
    )

    @api.depends('file', 'file_name')
    def _compute_file_details(self):
        for rec in self:
            ext = ''
            if rec.file_name and '.' in rec.file_name:
                ext = rec.file_name.rsplit('.', 1)[-1].upper()
            rec.file_ext_display = ext

            if rec.file:
                try:
                    raw = base64.b64decode(rec.file)
                    size_bytes = len(raw)
                    if size_bytes < 1024:
                        rec.file_size_display = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        rec.file_size_display = f"{size_bytes / 1024:.1f} KB"
                    else:
                        rec.file_size_display = f"{size_bytes / (1024 * 1024):.1f} MB"
                except Exception:
                    rec.file_size_display = ''
            else:
                rec.file_size_display = ''

    def action_register_download(self):
        for rec in self:
            rec.sudo().write({'download_count': rec.download_count + 1})
