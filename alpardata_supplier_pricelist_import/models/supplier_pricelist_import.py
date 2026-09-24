from __future__ import annotations

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

from odoo.addons.alpardata_purchase_replacement_cost.tools import (
    cascade_equivalent_pct,
    compute_replacement_cost,
    parse_discount_cascade,
)

from ..tools.readers import normalize_header, parse_number, read_csv, read_xlsx

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

    # ── Vista previa ──────────────────────────────────────────────────────────
    def action_preview(self) -> None:
        self.ensure_one()
        if self.state not in ('draft', 'preview'):
            raise UserError(_('Sólo se puede generar la vista previa en borrador.'))
        self.line_ids.unlink()
        if self.mode == 'file':
            vals_list = self._preview_from_file()
        else:
            vals_list = self._preview_from_percent()
        self.env['supplier.pricelist.import.line'].create(vals_list)
        self.state = 'preview'

    def _seller_for(self, template):
        return template.with_company(self.company_id)._get_reference_cost_seller(
            partner=self.partner_id,
        )

    def _line_vals(self, seller, new_price, new_cascade=None, row_number=0, code=False) -> dict:
        """Valores de una línea con proveedor encontrado y precio válido."""
        old_price = seller.reference_cost
        old_cascade = seller.effective_discount_cascade or False
        cascade = old_cascade if new_cascade is None else (new_cascade or False)
        tmpl = seller.product_tmpl_id
        _net, new_replacement = compute_replacement_cost(
            new_price,
            cascade_equivalent_pct(parse_discount_cascade(cascade)),
            seller.effective_early_payment_pct,
            seller.effective_freight_pct,
            seller.effective_perception_pct,
            tmpl.internal_tax_pct,
        )
        changed = (
            float_compare(new_price, old_price, precision_digits=4) != 0
            or (cascade or False) != old_cascade
        )
        return {
            'import_id': self.id,
            'row_number': row_number,
            'code': code,
            'supplierinfo_id': seller.id,
            'product_tmpl_id': tmpl.id,
            'old_list_price': old_price,
            'new_list_price': new_price,
            'variation_pct': ((new_price / old_price) - 1) * 100 if old_price else 0.0,
            'old_cascade': old_cascade,
            'new_cascade': cascade,
            'old_replacement_cost': seller.replacement_cost,
            'new_replacement_cost': new_replacement,
            'status': 'change' if changed else 'unchanged',
            'to_apply': changed,
        }

    def _preview_from_percent(self) -> list[dict]:
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('company_id', 'in', [self.company_id.id, False]),
        ]
        if self.filter_categ_ids:
            domain.append(('product_tmpl_id.categ_id', 'child_of', self.filter_categ_ids.ids))
        if self.filter_tag_ids:
            domain.append(('product_tmpl_id.product_tag_ids', 'in', self.filter_tag_ids.ids))
        templates = self.env['product.supplierinfo'].search(domain).product_tmpl_id
        vals_list = []
        for tmpl in templates:
            seller = self._seller_for(tmpl)
            if not seller:
                continue
            new_price = seller.reference_cost * (1 + self.percent / 100)
            vals_list.append(self._line_vals(seller, new_price, code=seller.product_code))
        return vals_list

    def _read_file_rows(self):
        profile = self.profile_id
        if not profile or not self.file:
            raise UserError(_('Elegí un perfil y cargá el archivo.'))
        content = base64.b64decode(self.file)
        try:
            if profile.file_type == 'xlsx':
                return read_xlsx(content, profile.sheet_name, profile.header_row)
            return read_csv(
                content, profile.csv_delimiter or ';', profile.csv_encoding or 'utf-8',
                profile.header_row,
            )
        except (ValueError, UnicodeDecodeError, KeyError, OSError) as err:
            raise UserError(_('No se pudo leer el archivo: %s', err)) from err
        except Exception as err:  # openpyxl levanta errores propios con archivos rotos
            raise UserError(_('No se pudo leer el archivo: %s', err)) from err

    def _find_template(self, code: str):
        match_by = self.profile_id.match_by
        if match_by == 'supplier_code':
            sellers = self.env['product.supplierinfo'].search([
                ('partner_id', '=', self.partner_id.id),
                ('product_code', '=', code),
                ('company_id', 'in', [self.company_id.id, False]),
            ])
            return sellers.product_tmpl_id[:1]
        field = 'barcode' if match_by == 'barcode' else 'default_code'
        return self.env['product.product'].search([(field, '=', code)], limit=1).product_tmpl_id

    def _preview_from_file(self) -> list[dict]:
        profile = self.profile_id
        rows = self._read_file_rows()
        col_code = normalize_header(profile.col_code)
        col_price = normalize_header(profile.col_price)
        col_cascade = normalize_header(profile.col_cascade) if profile.col_cascade else False
        headers = set(rows[0][1]) if rows else set()
        missing = [
            original for original, normalized in (
                (profile.col_code, col_code), (profile.col_price, col_price),
                (profile.col_cascade, col_cascade),
            ) if normalized and headers and normalized not in headers
        ]
        if missing:
            raise UserError(_(
                'Columnas no encontradas en el archivo: %s. Encabezados leídos: %s.',
                ', '.join(missing), ', '.join(sorted(headers)),
            ))
        decimal = profile.csv_decimal or ','
        seen: dict[str, int] = {}
        vals_list = []
        for row_number, data in rows:
            raw_code = data.get(col_code)
            if raw_code in (None, ''):
                continue
            code = str(raw_code).strip()
            if isinstance(raw_code, float) and raw_code.is_integer():
                code = str(int(raw_code))
            base = {'import_id': self.id, 'row_number': row_number, 'code': code}
            if code in seen:
                vals_list.append({**base, 'status': 'error',
                                  'message': _('Código duplicado en fila %s', seen[code])})
                continue
            seen[code] = row_number
            price = parse_number(data.get(col_price), decimal)
            if price is None or price <= 0:
                vals_list.append({**base, 'status': 'error',
                                  'message': _('Precio inválido: %s', data.get(col_price))})
                continue
            if profile.price_includes_vat:
                price = price / (1 + profile.vat_pct / 100)
            new_cascade = None
            if col_cascade:
                raw_cascade = data.get(col_cascade)
                new_cascade = str(raw_cascade).strip() if raw_cascade not in (None, '') else ''
                if isinstance(raw_cascade, float) and raw_cascade.is_integer():
                    new_cascade = str(int(raw_cascade))
                try:
                    parse_discount_cascade(new_cascade)
                except ValueError as err:
                    vals_list.append({**base, 'status': 'error', 'message': str(err)})
                    continue
            template = self._find_template(code)
            seller = self._seller_for(template) if template else False
            if not seller:
                vals_list.append({**base, 'status': 'not_found',
                                  'message': _('Producto o ficha del proveedor no encontrados')})
                continue
            vals_list.append(self._line_vals(seller, price, new_cascade, row_number, code))
        return vals_list

    # ── Aplicar ───────────────────────────────────────────────────────────────
    _COPIED_SELLER_FIELDS = (
        'partner_id', 'product_tmpl_id', 'product_id', 'company_id', 'product_code',
        'product_name', 'product_uom_id', 'currency_id', 'min_qty', 'sequence', 'delay',
        'price', 'discount', 'use_own_conditions', 'own_discount_cascade',
        'own_early_payment_pct', 'own_freight_pct', 'own_perception_pct',
    )

    def _new_seller_vals(self, line) -> dict:
        seller = line.supplierinfo_id
        vals = {}
        for name in self._COPIED_SELLER_FIELDS:
            value = seller[name]
            vals[name] = value.id if isinstance(value, models.BaseModel) else value
        vals.update({
            'reference_cost': line.new_list_price,
            'date_start': self.effective_date,
            'date_end': False,
        })
        if line.new_cascade != line.old_cascade:
            vals.update({
                'use_own_conditions': True,
                'own_discount_cascade': line.new_cascade or False,
            })
            if not seller.use_own_conditions:
                # Al pasar a condiciones propias se conservan las del proveedor
                vals.update({
                    'own_early_payment_pct': seller.effective_early_payment_pct,
                    'own_freight_pct': seller.effective_freight_pct,
                    'own_perception_pct': seller.effective_perception_pct,
                })
        return vals

    def action_apply(self) -> None:
        self.ensure_one()
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError(_('Sólo los gerentes de compras pueden aplicar listas de proveedores.'))
        if self.state != 'preview':
            raise UserError(_('Generá la vista previa antes de aplicar.'))
        lines = self.line_ids.filtered(lambda l: l.status == 'change' and l.to_apply)
        vals_list = [self._new_seller_vals(line) for line in lines]
        self.env['product.supplierinfo'].with_context(
            _change_reason=_('Importación %s', self.name),
        ).create(vals_list)
        self.write({
            'state': 'done',
            'applied_date': fields.Datetime.now(),
            'applied_by': self.env.uid,
        })
        self.message_post(body=_(
            'Lista aplicada: %(applied)s fichas actualizadas desde %(date)s '
            '(%(skipped)s cambios no aplicados, %(nf)s no encontrados, %(err)s errores).',
            applied=len(lines), date=self.effective_date,
            skipped=self.count_change - len(lines),
            nf=self.count_not_found, err=self.count_error,
        ))

    def action_cancel(self) -> None:
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('No se puede cancelar una importación aplicada.'))
        self.write({'state': 'cancelled'})

    def action_reset_draft(self) -> None:
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})
