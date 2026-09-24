from __future__ import annotations

from odoo.tests.common import TransactionCase


class PriceWatchCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor Góndola'})
        cls.categ = cls.env['product.category'].create({
            'name': 'Almacén Test', 'target_markup_pct': 40.0,
        })
        cls.tax = cls.env['account.tax'].create({
            'name': 'IVA 21 incluido test',
            'amount': 21.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'company_id': cls.company.id,
        })
        cls.template = cls.env['product.template'].create({
            'name': 'Fideos 500g',
            'categ_id': cls.categ.id,
            'list_price': 1694.0,  # 1400 sin IVA
            'taxes_id': [(6, 0, cls.tax.ids)],
            'sale_ok': True,
        })
        cls.seller = cls.env['product.supplierinfo'].create({
            'partner_id': cls.partner.id,
            'product_tmpl_id': cls.template.id,
            'price': 1000.0,
            'reference_cost': 1000.0,
        })
        cls.watch_model = cls.env['product.price.watch']

    def _watch(self, template=None):
        return self.watch_model._refresh(template or self.template, self.company)
