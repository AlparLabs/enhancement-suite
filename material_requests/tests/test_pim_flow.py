from odoo.tests.common import TransactionCase
from odoo.tests import tagged

@tagged('post_install', '-at_install')
class TestPimFlow(TransactionCase):

    def setUp(self):
        super(TestPimFlow, self).setUp()
        self.pim_model = self.env['pim']
        self.sim_model = self.env['sim']
        self.product_model = self.env['product.product']
        self.stock_location = self.env.ref('stock.stock_location_stock')
        
        # Create a Test Product
        self.product = self.product_model.create({
            'name': 'Test Material',
            'type': 'product', # Storable
        })

    def test_availability_split(self):
        """ Test that PIM splits correctly based on STOCK availability """
        # Only 5 in stock
        self.env['stock.quant']._update_available_quantity(self.product, self.stock_location, 5.0)

        # Request 10
        pim = self.pim_model.create({
            'name': 'PIM-TEST-001',
            'project_id': self.env.ref('project.project_project_1').id, # Assuming demo data or existing project
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 10.0,
            })]
        })
        
        pim.action_submit()
        pim.action_process_pim()
        
        # Check Split
        # 1. Picking for 5
        self.assertTrue(pim.picking_ids, "Should have created a picking")
        self.assertEqual(pim.picking_ids.move_ids.product_uom_qty, 5.0, "Should transfer 5 units")
        
        # 2. SIM for 5
        sim = self.env['sim'].search([('pim_id', '=', pim.id)])
        self.assertTrue(sim, "Should have created a SIM")
        self.assertEqual(sim.line_ids.quantity, 5.0, "SIM should be for remaining 5 units")

    def test_sim_po_vendor(self):
        """ Test that SIM creates PO with correct Vendor """
        vendor = self.env['res.partner'].create({'name': 'Test Vendor', 'supplier_rank': 1})
        
        sim = self.sim_model.create({
            'name': 'SIM-TEST-002',
            'partner_id': vendor.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 10.0,
            })]
        })
        
        res = sim.action_create_rfq()
        po_id = res['res_id']
        po = self.env['purchase.order'].browse(po_id)
        
        self.assertEqual(po.partner_id.id, vendor.id, "PO should use the Vendor from SIM")
