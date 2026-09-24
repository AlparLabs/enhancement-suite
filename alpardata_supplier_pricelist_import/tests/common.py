from __future__ import annotations

import base64
import io

import openpyxl

from odoo.tests.common import TransactionCase


def xlsx_b64(rows):
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue())


class ImportCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Distribuidora Test',
            'purchase_discount_cascade': '10',
        })
        cls.categ = cls.env['product.category'].create({'name': 'Gaseosas Test'})
        cls.categ_child = cls.env['product.category'].create({
            'name': 'Colas Test', 'parent_id': cls.categ.id,
        })
        cls.other_categ = cls.env['product.category'].create({'name': 'Otros Test'})
        cls.p1 = cls._product('Cola 2L', cls.categ_child, barcode='7790001', default_code='COLA2')
        cls.p2 = cls._product('Lima 2L', cls.categ, barcode='7790002', default_code='LIMA2')
        cls.p3 = cls._product('Yerba 1kg', cls.other_categ, barcode='7790003', default_code='YER1')
        cls.s1 = cls._seller(cls.p1, 'A1', 100.0)
        cls.s2 = cls._seller(cls.p2, 'A2', 200.0)
        cls.s3 = cls._seller(cls.p3, 'A3', 300.0)
        cls.profile = cls.env['supplier.pricelist.import.profile'].create({
            'name': 'Excel Distribuidora',
            'partner_id': cls.partner.id,
            'col_code': 'Código',
            'col_price': 'Precio',
        })

    @classmethod
    def _product(cls, name, categ, **vals):
        return cls.env['product.product'].create({'name': name, 'categ_id': categ.id, **vals})

    @classmethod
    def _seller(cls, product, code, cost):
        return cls.env['product.supplierinfo'].create({
            'partner_id': cls.partner.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_code': code,
            'price': cost,
            'reference_cost': cost,
        })

    def _file_import(self, rows, **vals):
        return self.env['supplier.pricelist.import'].create({
            'partner_id': self.partner.id,
            'mode': 'file',
            'profile_id': self.profile.id,
            'file': xlsx_b64(rows),
            'file_name': 'lista.xlsx',
            **vals,
        })

    def _line(self, imp, code):
        return imp.line_ids.filtered(lambda l: l.code == code)
