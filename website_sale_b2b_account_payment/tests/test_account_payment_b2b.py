# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase


class TestB2BAccountPayment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Franquicia Mendoza Centro',
            'company_id': cls.company.id,
            'credit_limit': 100000.0,
        })
        cls.website = cls.env['website'].create({
            'name': 'Franquicias EntreDos',
            'company_id': cls.company.id,
            'b2b_credit_block_active': True,
        })

    def test_01_b2b_payment_receipt_creation_and_activity(self):
        """Verifica la creación del comprobante de transferencia y la generación automática de la actividad contable."""
        receipt = self.env['b2b.payment.receipt'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'amount': 75000.0,
            'date': fields.Date.today(),
            'operation_number': 'TRF-123456789',
            'bank_origin': 'Banco Santander',
            'notes': 'Pago a cuenta de pedido semanal',
        })

        self.assertEqual(receipt.state, 'draft')
        self.assertTrue(receipt.name.startswith('TRF-'))
        self.assertEqual(receipt.amount, 75000.0)

        # Verificar que se programó la actividad automática para Tesorería
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'b2b.payment.receipt'),
            ('res_id', '=', receipt.id),
        ])
        self.assertEqual(len(activities), 1)
        self.assertIn('Franquicia Mendoza Centro', activities.summary)
        self.assertIn('TRF-123456789', activities.note)

    def test_02_b2b_payment_receipt_actions(self):
        """Verifica la aprobación y rechazo de comprobantes de transferencia."""
        receipt = self.env['b2b.payment.receipt'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'amount': 50000.0,
            'date': fields.Date.today(),
            'operation_number': 'TRF-999999',
        })

        # Aprobación
        receipt.action_verify()
        self.assertEqual(receipt.state, 'verified')
        self.assertEqual(receipt.verified_by, self.env.user)
        self.assertTrue(receipt.verified_date)

        # Volver a borrador
        receipt.action_set_to_draft()
        self.assertEqual(receipt.state, 'draft')

        # Rechazo con motivo
        receipt.action_reject(reason="El número de transferencia no coincide con el extracto bancario.")
        self.assertEqual(receipt.state, 'rejected')
        self.assertIn("no coincide", receipt.rejection_reason)

    def test_03_payment_reduces_debt_and_unblocks_partner(self):
        """Verifica que el impacto de un pago en cuenta corriente reduzca la deuda y desbloquee las compras."""
        # Al no tener facturas vencidas ni límite superado, el cliente está habilitado
        status_initial = self.partner._get_b2b_financial_status(self.website)
        self.assertFalse(status_initial['is_blocked'])
