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

    def test_reference_cost_respects_order_vendor(self):
        """Con varios proveedores, la línea toma el costo del proveedor de la
        orden, no el del proveedor principal (menor sequence)."""
        principal = self.env['res.partner'].create({'name': 'Proveedor Principal'})
        secundario = self.env['res.partner'].create({'name': 'Proveedor Secundario'})
        product = self.env['product.product'].create({'name': 'Producto multi proveedor'})
        self.env['product.supplierinfo'].create({
            'partner_id': principal.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'sequence': 1,
            'reference_cost': 16500.0,
        })
        self.env['product.supplierinfo'].create({
            'partner_id': secundario.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'sequence': 2,
            'reference_cost': 8800.0,
        })
        po = self.env['purchase.order'].create({'partner_id': secundario.id})
        line = self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': product.id,
            'product_qty': 1.0,
        })
        self.assertEqual(line.reference_cost, 8800.0)
        self.assertEqual(line.price_unit, 8800.0)

    def test_reference_cost_falls_back_to_parent_company(self):
        """En una sucursal sin proveedor propio, la linea toma el costo de
        referencia cargado en la empresa matriz para ese mismo proveedor
        (respeta la jerarquia de empresas y el proveedor de la orden)."""
        main = self.env['res.company'].create({'name': 'Matriz POL'})
        branch = self.env['res.company'].create({
            'name': 'Sucursal POL',
            'parent_id': main.id,
        })
        partner = self.env['res.partner'].create({'name': 'Proveedor Jerarquia'})
        product = self.env['product.product'].create({'name': 'Producto Jerarquia'})
        self.env['product.supplierinfo'].create({
            'partner_id': partner.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'company_id': main.id,
            'reference_cost': 12000.0,
        })
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'company_id': branch.id,
        })
        line = self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': product.id,
            'product_qty': 1.0,
        })
        self.assertEqual(line.reference_cost, 12000.0)
        self.assertEqual(line.price_unit, 12000.0)

    def test_catalog_adds_line_with_reference_cost(self):
        """Al agregar un producto desde el catalogo, el precio unitario toma el
        costo de referencia del proveedor de la orden (no el seller.price)."""
        po = self.env['purchase.order'].create({'partner_id': self.partner.id})
        po._update_order_line_info(self.product.id, 1)
        line = po.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(line.price_unit, 100.0)

    def test_catalog_card_price_uses_reference_cost(self):
        """La tarjeta del catalogo muestra el costo de referencia del proveedor
        de la orden, no el precio de lista del proveedor."""
        po = self.env['purchase.order'].create({'partner_id': self.partner.id})
        info = po._get_product_price_and_data(self.product)
        self.assertEqual(info['price'], 100.0)

    def test_catalog_without_reference_cost_keeps_seller_price(self):
        """Sin costo de referencia, el catalogo respeta el precio del proveedor."""
        product2 = self.env['product.product'].create({'name': 'Producto catalogo sin ref'})
        self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_tmpl_id': product2.product_tmpl_id.id,
            'price': 70.0,
        })
        po = self.env['purchase.order'].create({'partner_id': self.partner.id})
        po._update_order_line_info(product2.id, 1)
        line = po.order_line.filtered(lambda l: l.product_id == product2)
        self.assertEqual(line.price_unit, 70.0)

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
