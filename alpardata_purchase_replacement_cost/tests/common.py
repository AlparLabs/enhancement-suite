from __future__ import annotations

from odoo.tests.common import TransactionCase


class ReplacementCostCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor Cascada'})
        cls.categ = cls.env['product.category'].create({'name': 'Bebidas Test'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Reposición',
            'categ_id': cls.categ.id,
            'standard_price': 800.0,
        })
        cls.template = cls.product.product_tmpl_id

    @classmethod
    def _set_partner_conditions(cls, partner=None, cascade='10+5+3', early=2.0,
                                freight=3.5, perception=1.5):
        (partner or cls.partner).write({
            'purchase_discount_cascade': cascade,
            'purchase_early_payment_pct': early,
            'purchase_freight_pct': freight,
            'purchase_perception_pct': perception,
        })

    @classmethod
    def _add_seller(cls, reference_cost=1000.0, partner=None, **vals):
        return cls.env['product.supplierinfo'].create({
            'partner_id': (partner or cls.partner).id,
            'product_tmpl_id': cls.template.id,
            'price': reference_cost,
            'reference_cost': reference_cost,
            **vals,
        })
