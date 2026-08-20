from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestPurchaseMinimum(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.product = cls.env['product.product'].create({
            'name': 'Producto test',
            'purchase_method': 'purchase',
        })
        cls.approver_group = cls.env.ref(
            'purchase_minimum_approval.group_purchase_minimum_approver'
        )
        cls.approver = cls.env['res.users'].create({
            'name': 'Aprobador',
            'login': 'aprobador_min',
            'group_ids': [(6, 0, [cls.approver_group.id])],
        })
        cls.buyer = cls.env['res.users'].create({
            'name': 'Comprador',
            'login': 'comprador_min',
            'group_ids': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])],
        })

    def _make_partner(self, apply_minimum=False, minimum=0.0, parent=None):
        return self.env['res.partner'].create({
            'name': 'Proveedor test',
            'apply_purchase_minimum': apply_minimum,
            'purchase_minimum_amount': minimum,
            'parent_id': parent.id if parent else False,
        })

    def _make_po(self, partner, qty=1, price=100.0):
        return self.env['purchase.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'product_qty': qty,
                'price_unit': price,
                'product_uom': self.product.uom_id.id,
                'date_planned': '2026-07-20 00:00:00',
            })],
        })

    def test_no_minimum_confirms(self):
        partner = self._make_partner(apply_minimum=False)
        po = self._make_po(partner, price=10.0)
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_above_minimum_confirms(self):
        partner = self._make_partner(apply_minimum=True, minimum=50.0)
        po = self._make_po(partner, price=100.0)  # subtotal 100 >= 50
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_below_minimum_blocks(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)  # subtotal 100 < 500
        po.button_confirm()
        self.assertEqual(po.state, 'waiting_approval')
        self.assertTrue(po.minimum_approval_note)

    def test_approver_approves(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)
        po.button_confirm()
        self.assertEqual(po.state, 'waiting_approval')
        po.with_user(self.approver).action_approve_minimum()
        self.assertEqual(po.state, 'purchase')

    def test_non_approver_cannot_approve(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)
        po.button_confirm()
        with self.assertRaises(AccessError):
            po.with_user(self.buyer).action_approve_minimum()

    def test_parent_minimum_applies_to_child(self):
        parent = self._make_partner(apply_minimum=True, minimum=500.0)
        child = self._make_partner(apply_minimum=False, parent=parent)
        po = self._make_po(child, price=100.0)
        po.button_confirm()
        self.assertEqual(po.state, 'waiting_approval')

    def test_cancel_waiting_approval(self):
        partner = self._make_partner(apply_minimum=True, minimum=500.0)
        po = self._make_po(partner, price=100.0)
        po.button_confirm()
        po.button_cancel()
        self.assertEqual(po.state, 'cancel')
