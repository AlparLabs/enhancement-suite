from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPurchaseLineReferenceCost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor Test'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto con costo ref',
            'standard_price': 50.0,
        })
        cls.env['product.supplierinfo'].create({
            'partner_id': cls.partner.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'price': 80.0,
            'reference_cost': 100.0,
        })

    def _new_line(self, product, currency=None):
        vals = {'partner_id': self.partner.id}
        if currency:
            vals['currency_id'] = currency.id
        po = self.env['purchase.order'].create(vals)
        return self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': product.id,
            'product_qty': 1.0,
        })

    def test_price_unit_takes_reference_cost(self):
        """price_unit toma el costo de referencia, no el precio del proveedor."""
        line = self._new_line(self.product)
        self.assertEqual(line.price_unit, 100.0)

    def test_price_unit_is_editable(self):
        """El comprador puede pisar el precio a mano y persiste."""
        line = self._new_line(self.product)
        line.price_unit = 90.0
        self.assertEqual(line.price_unit, 90.0)

    def test_no_reference_cost_keeps_odoo_price(self):
        """Sin costo de referencia, se respeta el precio del proveedor de Odoo."""
        product2 = self.env['product.product'].create({'name': 'Producto sin costo ref'})
        self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_tmpl_id': product2.product_tmpl_id.id,
            'price': 70.0,
        })
        line = self._new_line(product2)
        self.assertEqual(line.price_unit, 70.0)

    def test_price_unit_currency_conversion(self):
        """El costo de referencia se convierte a la moneda de la orden."""
        company_currency = self.env.company.currency_id
        other = self.env['res.currency'].create({
            'name': 'TSTX',
            'symbol': 'T',
            'rounding': 0.01,
        })
        self.env['res.currency.rate'].create({
            'currency_id': other.id,
            'company_id': self.env.company.id,
            'rate': 2.0,  # 1 moneda-empresa = 2 TSTX
            'name': fields.Date.today(),
        })
        line = self._new_line(self.product, currency=other)
        if line.order_id.currency_id == other and other != company_currency:
            self.assertAlmostEqual(line.price_unit, 200.0, places=2)
        else:
            self.assertAlmostEqual(line.price_unit, 100.0, places=2)
