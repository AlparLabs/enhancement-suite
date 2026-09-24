from __future__ import annotations

import io

import openpyxl

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.alpardata_supplier_pricelist_import.tools.readers import (
    normalize_header,
    parse_number,
    read_csv,
    read_xlsx,
)


def make_xlsx(rows, sheet='Lista', leading_rows=0):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for _ in range(leading_rows):
        ws.append(['Lista de precios Proveedor SA'])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestReaders(BaseCase):

    def test_normalize_header(self):
        self.assertEqual(normalize_header('  Código  Artículo '), 'codigo articulo')
        self.assertEqual(normalize_header('PRECIO'), 'precio')
        self.assertEqual(normalize_header(None), '')

    def test_parse_number(self):
        self.assertEqual(parse_number(12.5, ','), 12.5)
        self.assertEqual(parse_number('1.234,50', ','), 1234.5)
        self.assertEqual(parse_number('1,234.50', '.'), 1234.5)
        self.assertEqual(parse_number('$ 99,9', ','), 99.9)
        self.assertIsNone(parse_number('abc', ','))
        self.assertIsNone(parse_number('', ','))
        self.assertIsNone(parse_number(None, ','))

    def test_read_xlsx_with_header_row(self):
        content = make_xlsx(
            [['Código', 'Descripción', 'Precio'], ['A1', 'Coca', 100], ['A2', 'Fanta', '90,5']],
            leading_rows=2,
        )
        rows = read_xlsx(content, sheet_name='Lista', header_row=3)
        self.assertEqual(rows[0], (4, {'codigo': 'A1', 'descripcion': 'Coca', 'precio': 100}))
        self.assertEqual(rows[1][0], 5)
        self.assertEqual(rows[1][1]['precio'], '90,5')

    def test_read_xlsx_missing_sheet(self):
        content = make_xlsx([['Código', 'Precio']])
        with self.assertRaises(ValueError):
            read_xlsx(content, sheet_name='Otra', header_row=1)

    def test_read_xlsx_first_sheet_by_default(self):
        content = make_xlsx([['Código', 'Precio'], ['A1', 10]])
        rows = read_xlsx(content, sheet_name=False, header_row=1)
        self.assertEqual(rows, [(2, {'codigo': 'A1', 'precio': 10})])

    def test_read_csv_latin1(self):
        content = 'Código;Precio\nA1;1.234,50\n\nA2;10\n'.encode('latin-1')
        rows = read_csv(content, delimiter=';', encoding='latin-1', header_row=1)
        self.assertEqual(rows, [
            (2, {'codigo': 'A1', 'precio': '1.234,50'}),
            (4, {'codigo': 'A2', 'precio': '10'}),
        ])
