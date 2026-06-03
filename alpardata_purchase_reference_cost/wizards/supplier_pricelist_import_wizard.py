import base64
import logging
from io import BytesIO, StringIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductSupplierPricelistImport(models.TransientModel):
    """
    Wizard para importar una lista de precios de proveedor (Excel o CSV)
    y actualizar el Costo de Referencia en product.supplierinfo.

    Por cada fila del archivo:
      - Busca el supplierinfo existente para (proveedor, producto).
      - Si existe → actualiza reference_cost (upsert: nunca crea duplicados).
      - Si no existe → crea un supplierinfo nuevo para ese proveedor+producto.

    Cuando el proveedor es el principal (menor sequence), el cambio se propaga
    automáticamente a product.template.reference_cost.

    Flujo:
        1. Configurar: archivo + mapeo de columnas.
        2. Vista previa: revisar cambios antes de aplicar.
        3. Aplicar.
    """

    _name = 'product.supplier.pricelist.import'
    _description = 'Importar Lista de Precios de Proveedor'

    # ── Encabezado ────────────────────────────────────────────────────────────
    supplier_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        domain=[('supplier_rank', '>', 0)],
        help='Proveedor del cual proviene la lista de precios.',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )

    # ── Archivo ───────────────────────────────────────────────────────────────
    file_data = fields.Binary(
        string='Archivo (Excel o CSV)',
        required=True,
        attachment=False,
    )
    file_name = fields.Char(string='Nombre del archivo')

    sheet_name = fields.Char(
        string='Hoja',
        default='',
        placeholder='Primera hoja si se deja vacío',
        help='Nombre o número de hoja. Vacío = primera hoja.',
    )

    header_row = fields.Integer(
        string='Fila de encabezados',
        default=1,
        help='Número de fila donde están los títulos (1 = primera fila).',
    )

    # ── Mapeo de columnas ─────────────────────────────────────────────────────
    match_field = fields.Selection(
        selection=[
            ('default_code', 'Referencia interna del producto'),
            ('barcode', 'Código de barras / EAN'),
            ('supplier_code', 'Código del proveedor (en ficha del producto)'),
        ],
        string='Identificar producto por',
        required=True,
        default='default_code',
    )

    col_identifier = fields.Char(
        string='Columna del identificador',
        required=True,
        help=(
            'Letra de columna Excel (ej: A, B, C) '
            'o nombre exacto del encabezado (ej: "Código").'
        ),
    )

    col_price = fields.Char(
        string='Columna del precio de referencia',
        required=True,
        help=(
            'Letra de columna Excel (ej: B, C) '
            'o nombre exacto del encabezado (ej: "Precio Lista").'
        ),
    )

    notes = fields.Text(
        string='Justificación',
        help='Aparece en el historial de cambios de cada producto.',
    )

    # ── Preview ───────────────────────────────────────────────────────────────
    preview_line_ids = fields.One2many(
        'product.supplier.pricelist.import.line',
        'wizard_id',
        string='Vista previa',
        readonly=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Configurar'),
            ('preview', 'Revisar y aplicar'),
        ],
        default='draft',
    )

    found_count = fields.Integer(
        string='Productos encontrados',
        compute='_compute_summary',
    )
    not_found_count = fields.Integer(
        string='No encontrados',
        compute='_compute_summary',
    )
    no_price_count = fields.Integer(
        string='Sin precio',
        compute='_compute_summary',
    )
    new_supplier_count = fields.Integer(
        string='Proveedores nuevos a crear',
        compute='_compute_summary',
    )

    @api.depends('preview_line_ids.status', 'preview_line_ids.is_new_supplierinfo')
    def _compute_summary(self):
        for rec in self:
            lines = rec.preview_line_ids
            rec.found_count = len(lines.filtered(lambda l: l.status == 'found'))
            rec.not_found_count = len(lines.filtered(lambda l: l.status == 'not_found'))
            rec.no_price_count = len(lines.filtered(lambda l: l.status == 'no_price'))
            rec.new_supplier_count = len(
                lines.filtered(lambda l: l.status == 'found' and l.is_new_supplierinfo)
            )

    # ── Column / file parsing ─────────────────────────────────────────────────

    def _resolve_column(self, col_spec: str, headers: list) -> int:
        """
        Converts a column spec to a 0-based index.
        Accepts: Excel letter (A, B, AA), column number (1, 2), or header name.
        """
        spec = col_spec.strip()

        if spec.upper().isalpha():
            idx = 0
            for char in spec.upper():
                idx = idx * 26 + (ord(char) - ord('A') + 1)
            return idx - 1

        try:
            return int(spec) - 1
        except ValueError:
            pass

        spec_lower = spec.lower()
        for i, h in enumerate(headers):
            if h.lower() == spec_lower:
                return i

        available = ', '.join(f'"{h}"' for h in headers if h) or '(sin encabezados)'
        raise UserError(
            _('No se encontró la columna "%(col)s".\nColumnas disponibles: %(av)s',
              col=spec, av=available)
        )

    def _clean_price(self, raw) -> float | None:
        """Converts a raw cell value to float, handling Argentine number formats."""
        if raw is None or raw == '':
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        for char in ('$', ' ', '\xa0'):
            text = text.replace(char, '')
        if not text:
            return None
        # Argentine format: 1.500,00 → 1500.00
        if ',' in text and '.' in text:
            if text.index('.') < text.index(','):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            text = text.replace(',', '.')
        try:
            return float(text)
        except ValueError:
            return None

    def _parse_rows(self) -> list[dict]:
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Por favor, cargá un archivo.'))

        raw_bytes = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()

        if fname.endswith('.csv'):
            return self._parse_csv(raw_bytes)
        return self._parse_xlsx(raw_bytes)

    def _parse_xlsx(self, raw_bytes: bytes) -> list[dict]:
        try:
            import openpyxl
        except ImportError as exc:
            raise UserError(
                _('La librería openpyxl no está disponible en este entorno de Odoo.')
            ) from exc

        wb = openpyxl.load_workbook(BytesIO(raw_bytes), data_only=True)

        if self.sheet_name:
            try:
                ws = wb[self.sheet_name]
            except KeyError:
                try:
                    ws = wb.worksheets[int(self.sheet_name) - 1]
                except (ValueError, IndexError) as exc:
                    raise UserError(
                        _('No se encontró la hoja "%(name)s". Hojas disponibles: %(sheets)s',
                          name=self.sheet_name, sheets=', '.join(wb.sheetnames))
                    ) from exc
        else:
            ws = wb.active

        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            raise UserError(_('El archivo Excel está vacío.'))

        header_idx = self.header_row - 1
        if header_idx >= len(all_rows):
            raise UserError(
                _('La fila de encabezados (%(row)d) supera el total de filas.',
                  row=self.header_row)
            )

        headers = [str(h).strip() if h is not None else '' for h in all_rows[header_idx]]
        col_id_idx = self._resolve_column(self.col_identifier, headers)
        col_price_idx = self._resolve_column(self.col_price, headers)

        result = []
        for row in all_rows[header_idx + 1:]:
            if all(cell is None for cell in row):
                continue
            identifier = row[col_id_idx] if col_id_idx < len(row) else None
            price_raw = row[col_price_idx] if col_price_idx < len(row) else None
            if identifier is None:
                continue
            result.append({
                'identifier': str(identifier).strip(),
                'price': self._clean_price(price_raw),
            })
        return result

    def _parse_csv(self, raw_bytes: bytes) -> list[dict]:
        import csv

        content = None
        for encoding in ('utf-8-sig', 'latin-1', 'utf-8'):
            try:
                content = raw_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise UserError(_('No se pudo leer el CSV. Guardalo en UTF-8 o Latin-1.'))

        sample = content[:2048]
        delimiter = ';' if sample.count(';') > sample.count(',') else ','

        reader = csv.reader(StringIO(content), delimiter=delimiter)
        all_rows = list(reader)
        if not all_rows:
            raise UserError(_('El archivo CSV está vacío.'))

        header_idx = self.header_row - 1
        headers = [h.strip() for h in all_rows[header_idx]]
        col_id_idx = self._resolve_column(self.col_identifier, headers)
        col_price_idx = self._resolve_column(self.col_price, headers)

        result = []
        for row in all_rows[header_idx + 1:]:
            if not any(cell.strip() for cell in row):
                continue
            identifier = row[col_id_idx].strip() if col_id_idx < len(row) else ''
            price_raw = row[col_price_idx].strip() if col_price_idx < len(row) else ''
            if not identifier:
                continue
            result.append({
                'identifier': identifier,
                'price': self._clean_price(price_raw),
            })
        return result

    # ── Product / supplierinfo lookup ─────────────────────────────────────────

    def _find_product_tmpl(self, identifier: str):
        if self.match_field == 'default_code':
            return self.env['product.template'].search(
                [('default_code', '=', identifier)], limit=1
            )
        if self.match_field == 'barcode':
            variant = self.env['product.product'].search(
                [('barcode', '=', identifier)], limit=1
            )
            return variant.product_tmpl_id if variant else self.env['product.template']
        if self.match_field == 'supplier_code':
            sinfo = self.env['product.supplierinfo'].search([
                ('product_code', '=', identifier),
                ('partner_id', '=', self.supplier_id.id),
            ], limit=1)
            return sinfo.product_tmpl_id if sinfo else self.env['product.template']
        return self.env['product.template']

    def _find_existing_supplierinfo(self, product_tmpl):
        """
        Returns the existing supplierinfo for (supplier, product, company).
        Upsert target: update this record instead of creating a new one.
        Matches on (partner_id, product_tmpl_id) with company scope.
        """
        domain = [
            ('partner_id', '=', self.supplier_id.id),
            ('product_tmpl_id', '=', product_tmpl.id),
            '|',
            ('company_id', '=', self.company_id.id),
            ('company_id', '=', False),
        ]
        return self.env['product.supplierinfo'].search(domain, order='sequence asc', limit=1)

    # ── Wizard actions ────────────────────────────────────────────────────────

    def action_preview(self):
        """Parse the file and populate preview lines."""
        self.ensure_one()
        rows = self._parse_rows()

        self.preview_line_ids.unlink()

        lines = []
        for row in rows:
            identifier = row['identifier']
            new_cost = row['price']
            product = self._find_product_tmpl(identifier)

            if not product:
                lines.append({
                    'wizard_id': self.id,
                    'product_tmpl_id': False,
                    'supplierinfo_id': False,
                    'identifier_value': identifier,
                    'current_reference_cost': 0.0,
                    'new_reference_cost': new_cost or 0.0,
                    'is_new_supplierinfo': False,
                    'status': 'not_found',
                })
                continue

            sinfo = self._find_existing_supplierinfo(product)
            is_new = not bool(sinfo)

            if not new_cost:
                status = 'no_price'
            else:
                status = 'found'

            lines.append({
                'wizard_id': self.id,
                'product_tmpl_id': product.id,
                'supplierinfo_id': sinfo.id if sinfo else False,
                'identifier_value': identifier,
                'current_reference_cost': sinfo.reference_cost if sinfo else 0.0,
                'new_reference_cost': new_cost or 0.0,
                'is_new_supplierinfo': is_new,
                'status': status,
            })

        self.env['product.supplier.pricelist.import.line'].create(lines)
        self.state = 'preview'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back(self):
        self.ensure_one()
        self.state = 'draft'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        """
        Upsert reference_cost on product.supplierinfo for each 'found' line.
        If no supplierinfo exists yet for the supplier+product, creates one.
        """
        self.ensure_one()

        valid_lines = self.preview_line_ids.filtered(
            lambda l: l.status == 'found' and l.product_tmpl_id and l.new_reference_cost > 0
        )

        if not valid_lines:
            raise UserError(
                _('No hay productos válidos para actualizar. '
                  'Revisá la configuración de columnas o el archivo.')
            )

        reason = self.notes or _(
            'Importación lista de precios — %(supplier)s',
            supplier=self.supplier_id.name,
        )

        updated = 0
        created = 0

        for line in valid_lines:
            if line.supplierinfo_id:
                # Update existing supplierinfo (upsert)
                line.supplierinfo_id.with_context(
                    _change_reason=reason,
                ).write({'reference_cost': line.new_reference_cost})
                updated += 1
            else:
                # Create new supplierinfo for this supplier+product
                self.env['product.supplierinfo'].with_context(
                    _change_reason=reason,
                ).create({
                    'partner_id': self.supplier_id.id,
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'company_id': self.company_id.id,
                    'reference_cost': line.new_reference_cost,
                    'price': 0.0,
                })
                created += 1

        parts = []
        if updated:
            parts.append(_('%(n)d actualizado(s)', n=updated))
        if created:
            parts.append(_('%(n)d creado(s) como nuevo proveedor', n=created))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación completada'),
                'message': _(
                    'Costo de Referencia procesado: %(detail)s.',
                    detail=', '.join(parts),
                ),
                'type': 'success',
                'sticky': False,
            },
        }


class ProductSupplierPricelistImportLine(models.TransientModel):
    """Preview lines for supplier pricelist import."""

    _name = 'product.supplier.pricelist.import.line'
    _description = 'Línea de previsualización — Importación Lista de Precios'
    _order = 'status asc, identifier_value asc'

    wizard_id = fields.Many2one(
        'product.supplier.pricelist.import',
        required=True,
        ondelete='cascade',
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        readonly=True,
    )

    supplierinfo_id = fields.Many2one(
        'product.supplierinfo',
        string='Ficha proveedor existente',
        readonly=True,
    )

    is_new_supplierinfo = fields.Boolean(
        string='Nuevo proveedor en producto',
        readonly=True,
        help='Verdadero si no existe aún un supplierinfo para este proveedor+producto.',
    )

    identifier_value = fields.Char(
        string='Identificador (archivo)',
        readonly=True,
    )

    current_reference_cost = fields.Float(
        string='Costo Ref. actual',
        digits='Product Price',
        readonly=True,
    )

    new_reference_cost = fields.Float(
        string='Nuevo Costo Ref.',
        digits='Product Price',
        readonly=True,
    )

    status = fields.Selection(
        selection=[
            ('found', 'Encontrado'),
            ('not_found', 'No encontrado'),
            ('no_price', 'Sin precio'),
        ],
        string='Estado',
        readonly=True,
    )

    diff_pct = fields.Float(
        string='Variación %',
        compute='_compute_diff',
        digits=(5, 1),
    )

    @api.depends('current_reference_cost', 'new_reference_cost')
    def _compute_diff(self):
        for rec in self:
            if rec.current_reference_cost:
                rec.diff_pct = (
                    (rec.new_reference_cost - rec.current_reference_cost)
                    / rec.current_reference_cost * 100
                )
            else:
                rec.diff_pct = 0.0
