from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestProductChannelAssignWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website_franq = cls.env['website'].create({'name': 'Canal Franquicias'})
        cls.website_dist = cls.env['website'].create({'name': 'Canal Distribución'})

        cls.product_tmpl_1 = cls.env['product.template'].create({
            'name': 'Alfajor Chocolate Franquicia Test',
            'list_price': 1000.0,
        })
        cls.product_tmpl_2 = cls.env['product.template'].create({
            'name': 'Alfajor Dulce de Leche Test',
            'list_price': 1200.0,
        })

    def test_01_assign_specific_channel(self):
        """Asignar masivamente productos a un canal específico."""
        wizard = self.env['product.channel.assign.wizard'].with_context(
            active_model='product.template',
            active_ids=[self.product_tmpl_1.id, self.product_tmpl_2.id],
        ).create({
            'action_type': 'assign',
            'website_id': self.website_franq.id,
        })

        self.assertEqual(wizard.product_count, 2)
        wizard.action_apply()

        self.assertEqual(self.product_tmpl_1.website_id, self.website_franq)
        self.assertEqual(self.product_tmpl_2.website_id, self.website_franq)

    def test_02_clear_channel_shared(self):
        """Habilitar masivamente productos para todos los canales (website_id = False)."""
        self.product_tmpl_1.website_id = self.website_franq

        wizard = self.env['product.channel.assign.wizard'].with_context(
            active_model='product.template',
            active_ids=[self.product_tmpl_1.id],
        ).create({
            'action_type': 'clear',
        })

        wizard.action_apply()
        self.assertFalse(self.product_tmpl_1.website_id)

    def test_03_launch_from_variants(self):
        """El asistente resuelve correctamente las plantillas si se ejecuta desde variantes de producto."""
        variant_1 = self.product_tmpl_1.product_variant_id
        variant_2 = self.product_tmpl_2.product_variant_id

        wizard = self.env['product.channel.assign.wizard'].with_context(
            active_model='product.product',
            active_ids=[variant_1.id, variant_2.id],
        ).create({
            'action_type': 'assign',
            'website_id': self.website_dist.id,
        })

        self.assertEqual(set(wizard.product_tmpl_ids.ids), {self.product_tmpl_1.id, self.product_tmpl_2.id})
        wizard.action_apply()
        self.assertEqual(self.product_tmpl_1.website_id, self.website_dist)
        self.assertEqual(self.product_tmpl_2.website_id, self.website_dist)

    def test_04_validation_requires_website(self):
        """Debe arrojar UserError si se intenta asignar a un canal sin especificar el sitio."""
        wizard = self.env['product.channel.assign.wizard'].with_context(
            active_model='product.template',
            active_ids=[self.product_tmpl_1.id],
        ).create({
            'action_type': 'assign',
            'website_id': False,
        })

        with self.assertRaises(UserError):
            wizard.action_apply()
