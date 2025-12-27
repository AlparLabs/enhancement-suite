# account_payment_lock_3way/tests/test_payment_lock.py
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields

@tagged('post_install', '-at_install')
class TestPaymentLock3Way(TransactionCase):

    def setUp(self):
        super(TestPaymentLock3Way, self).setUp()
        
        # 1. CREAMOS DATOS DE PRUEBA
        # Un producto, un proveedor y un diario de banco
        self.partner = self.env['res.partner'].create({'name': 'Proveedor Test'})
        self.product = self.env['product.product'].create({
            'name': 'Producto Test',
            'type': 'product', # Almacenable
            'standard_price': 100.0,
        })
        self.bank_journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)

    def test_block_payment_price_discrepancy(self):
        """ Caso 1: Bloquear pago si el precio de factura es mayor a la PO """
        
        # A. Crear Orden de Compra (PO) a $100
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10.0,
                'price_unit': 100.0, # Precio Acordado
            })],
        })
        po.button_confirm()
        
        # B. Recibir la mercancía (Stock)
        picking = po.picking_ids
        picking.button_validate()

        # C. Crear Factura pero con precio $150 (DISCREPANCIA)
        # Odoo detectará esto y pondrá release_to_pay = 'exception'
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 10.0,
                'price_unit': 150.0, # Precio Inflado
                'purchase_line_id': po.order_line.id, # Vinculamos a la PO
            })],
        })
        invoice.action_post()

        # D. Intentar Pagar -> DEBE FALLAR
        # Usamos 'with self.assertRaises(UserError)' para decirle al test:
        # "Espero que la siguiente línea de error. Si no da error, avísame".
        with self.assertRaises(UserError, msg="El pago debió bloquearse por precio alto"):
            invoice.action_register_payment()
            
        print("✅ Test 1 Pasado: El sistema bloqueó el pago correctamente.")

    def test_allow_payment_with_approval(self):
        """ Caso 2: Permitir pago si el Gerente aprueba """
        
        # Repetimos el escenario de error...
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_qty': 1, 'price_unit': 100})],
        })
        po.button_confirm()
        po.picking_ids.button_validate()
        
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 
                'quantity': 1, 
                'price_unit': 200, # Precio Inflado
                'purchase_line_id': po.order_line.id
            })],
        })
        invoice.action_post()

        # ... Pero ahora ACTIVAMOS LA APROBACIÓN
        invoice.x_force_payment_approved = True
        
        # Intentar pagar -> DEBE FUNCIONAR (No debe dar error)
        try:
            invoice.action_register_payment()
        except UserError:
            self.fail("El pago falló incluso con la aprobación del gerente activada.")
            
        print("✅ Test 2 Pasado: El sistema permitió el pago con autorización.")