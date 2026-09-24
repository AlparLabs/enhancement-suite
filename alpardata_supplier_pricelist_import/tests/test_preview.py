from __future__ import annotations

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ImportCommon


@tagged('post_install', '-at_install')
class TestPreview(ImportCommon):

    def test_statuses(self):
        imp = self._file_import([
            ['Código', 'Precio'],
            ['A1', 110],        # cambia
            ['A2', 200],        # sin cambio
            ['ZZ', 50],         # no encontrado
            ['A3', 'abc'],      # error
            ['A1', 120],        # duplicado
            [None, 999],        # sin código: se ignora
        ])
        imp.action_preview()
        self.assertEqual(imp.state, 'preview')
        self.assertEqual(self._line(imp, 'A1').mapped('status'), ['change', 'error'])
        self.assertEqual(self._line(imp, 'A2').status, 'unchanged')
        self.assertEqual(self._line(imp, 'ZZ').status, 'not_found')
        self.assertEqual(self._line(imp, 'A3').status, 'error')
        self.assertEqual(len(imp.line_ids), 5)

    def test_change_values(self):
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]])
        imp.action_preview()
        line = self._line(imp, 'A1')
        self.assertEqual(line.supplierinfo_id, self.s1)
        self.assertEqual(line.old_list_price, 100.0)
        self.assertEqual(line.new_list_price, 110.0)
        self.assertAlmostEqual(line.variation_pct, 10.0)
        # bonificación del proveedor 10 %
        self.assertAlmostEqual(line.old_replacement_cost, 90.0)
        self.assertAlmostEqual(line.new_replacement_cost, 99.0)
        self.assertTrue(line.to_apply)

    def test_match_by_barcode_and_default_code(self):
        self.profile.match_by = 'barcode'
        imp = self._file_import([['Código', 'Precio'], ['7790001', 110]])
        imp.action_preview()
        self.assertEqual(self._line(imp, '7790001').supplierinfo_id, self.s1)
        self.profile.match_by = 'default_code'
        imp2 = self._file_import([['Código', 'Precio'], ['LIMA2', 210]])
        imp2.action_preview()
        self.assertEqual(self._line(imp2, 'LIMA2').supplierinfo_id, self.s2)

    def test_price_includes_vat(self):
        self.profile.price_includes_vat = True
        imp = self._file_import([['Código', 'Precio'], ['A1', 121]])
        imp.action_preview()
        self.assertAlmostEqual(self._line(imp, 'A1').new_list_price, 100.0)
        self.assertEqual(self._line(imp, 'A1').status, 'unchanged')

    def test_cascade_column(self):
        self.profile.col_cascade = 'Bonif'
        imp = self._file_import([['Código', 'Precio', 'Bonif'], ['A1', 100, '20']])
        imp.action_preview()
        line = self._line(imp, 'A1')
        self.assertEqual(line.status, 'change')
        self.assertEqual(line.old_cascade, '10')
        self.assertEqual(line.new_cascade, '20')
        self.assertAlmostEqual(line.new_replacement_cost, 80.0)

    def test_missing_column(self):
        imp = self._file_import([['Cod', 'Precio'], ['A1', 1]])
        with self.assertRaises(UserError):
            imp.action_preview()

    def test_percent_mode_with_filters(self):
        imp = self.env['supplier.pricelist.import'].create({
            'partner_id': self.partner.id,
            'mode': 'percent',
            'percent': 8.0,
            'filter_categ_ids': [(6, 0, self.categ.ids)],
        })
        imp.action_preview()
        self.assertEqual(
            imp.line_ids.mapped('supplierinfo_id'), self.s1 | self.s2,
            'Incluye la subcategoría y excluye otras categorías',
        )
        self.assertAlmostEqual(self._line(imp, 'A1').new_list_price, 108.0)

    def test_preview_regenerates(self):
        imp = self._file_import([['Código', 'Precio'], ['A1', 110]])
        imp.action_preview()
        imp.action_preview()
        self.assertEqual(len(imp.line_ids), 1)
