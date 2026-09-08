from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestB2BWebsiteAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website_1 = cls.env['website'].create({'name': 'Canal Franquicias'})
        cls.website_2 = cls.env['website'].create({'name': 'Canal Distribución'})

        # Usuario interno (Admin)
        cls.user_admin = cls.env.ref('base.user_admin')

        # Contacto portal Franquicia
        cls.partner_franq = cls.env['res.partner'].create({
            'name': 'Cliente Franquicia Test',
            'b2b_website_ids': [(6, 0, [cls.website_1.id])],
        })
        cls.user_franq = cls.env['res.users'].create({
            'name': 'Usuario Franquicia',
            'login': 'franq_test@entrededos.com.ar',
            'partner_id': cls.partner_franq.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def test_01_internal_user_has_access_everywhere(self):
        """Usuarios internos siempre tienen acceso a ambos sitios."""
        self.assertTrue(self.website_1.with_user(self.user_admin).has_ecommerce_access())
        self.assertTrue(self.website_2.with_user(self.user_admin).has_ecommerce_access())

    def test_02_portal_user_access_restricted_to_own_channel(self):
        """Usuario de portal solo tiene acceso al sitio de su canal."""
        self.assertTrue(self.website_1.with_user(self.user_franq).has_ecommerce_access())
        self.assertFalse(self.website_2.with_user(self.user_franq).has_ecommerce_access())

    def test_03_partner_base_url_resolves_assigned_website(self):
        """La URL base de un contacto con canal asignado apunta a su website."""
        self.website_1.domain = 'https://franquicias.entrededos.com.ar'
        self.assertEqual(self.partner_franq.get_base_url(), 'https://franquicias.entrededos.com.ar')
