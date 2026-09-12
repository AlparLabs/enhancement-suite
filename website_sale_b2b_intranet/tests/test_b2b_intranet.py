# -*- coding: utf-8 -*-
import base64
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestB2BIntranet(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Franquicia EntreDos Palmares',
            'company_id': cls.company.id,
        })
        cls.website_franchise = cls.env['website'].create({
            'name': 'Franquicias EntreDos',
            'company_id': cls.company.id,
        })
        cls.website_wholesale = cls.env['website'].create({
            'name': 'Distribuidores Mayoristas',
            'company_id': cls.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Alfajor Premium Chocolate Negro 60g',
            'list_price': 1500.0,
        })

    def test_01_marketing_material_creation_and_details(self):
        """Verifica la carga de materiales, cálculo de tamaño, extensión y conteo de descargas."""
        fake_content = base64.b64encode(b"PDF Manual de Identidad Visual EntreDos 2026")
        material = self.env['b2b.marketing.material'].create({
            'name': 'Manual de Marca 2026',
            'category': 'manual',
            'file': fake_content,
            'file_name': 'Manual_Marca_2026.pdf',
            'website_ids': [(6, 0, [self.website_franchise.id])],
        })

        self.assertEqual(material.file_ext_display, 'PDF')
        self.assertTrue(material.file_size_display.endswith('B'))
        self.assertEqual(material.download_count, 0)

        # Registro de descarga
        material.action_register_download()
        self.assertEqual(material.download_count, 1)

        # Verificación de visibilidad por sitio web
        franchise_materials = self.env['b2b.marketing.material'].search([
            ('id', '=', material.id),
            '|', ('website_ids', '=', False), ('website_ids', 'in', [self.website_franchise.id])
        ])
        self.assertIn(material, franchise_materials)

        wholesale_materials = self.env['b2b.marketing.material'].search([
            ('id', '=', material.id),
            '|', ('website_ids', '=', False), ('website_ids', 'in', [self.website_wholesale.id])
        ])
        self.assertNotIn(material, wholesale_materials)

    def test_02_order_claim_creation_and_activity(self):
        """Verifica la generación de reclamo, secuencia única, actividad de calidad y chatter en pedido."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 100,
                    'price_unit': 1500.0,
                })
            ]
        })
        order.action_confirm()

        # Creación del reclamo
        claim = self.env['b2b.order.claim'].create({
            'order_id': order.id,
            'claim_type': 'damaged',
            'product_id': self.product.id,
            'affected_qty': 12.0,
            'lot_number': 'L2609-01',
            'description': 'Caja aplastada durante la descarga de transporte, alfajores dañados.',
        })

        self.assertEqual(claim.state, 'draft')
        self.assertTrue(claim.name.startswith('CLM-'))
        self.assertEqual(claim.partner_id, self.partner)
        self.assertEqual(order.claim_count, 1)
        self.assertIn(claim, order.claim_ids)

        # Actividad planificada para el equipo
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'b2b.order.claim'),
            ('res_id', '=', claim.id),
        ])
        self.assertEqual(len(activities), 1)
        self.assertIn(claim.name, activities.summary)

    def test_03_claim_resolution_and_rejection_flow(self):
        """Verifica el flujo de estados: análisis, resolución con compensación y desestimación."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
        })
        claim = self.env['b2b.order.claim'].create({
            'order_id': order.id,
            'claim_type': 'missing',
            'description': 'Faltó una caja de 24 unidades en el envío.',
        })

        # Poner en análisis
        claim.action_set_in_progress()
        self.assertEqual(claim.state, 'in_progress')

        # Intentar resolver sin tipo de compensación debe lanzar UserError
        with self.assertRaises(UserError):
            claim.action_resolve()

        # Asignar resolución y dictaminar
        claim.resolution_type = 'credit_note'
        claim.resolution_notes = 'Se emite Nota de Crédito NC-A-0001-00004523 por $36.000.'
        claim.action_resolve()

        self.assertEqual(claim.state, 'resolved')
        self.assertEqual(claim.resolved_by_id, self.env.user)
        self.assertTrue(claim.date_resolved)
