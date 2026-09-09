# -*- coding: utf-8 -*-
from datetime import datetime
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestB2BOrderRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.website_franquicias = cls.env['website'].create({
            'name': 'Franquicias EntreDos',
            'company_id': cls.company.id,
            'b2b_order_schedule_active': True,
            'b2b_order_mon': True,
            'b2b_order_tue': True,
            'b2b_order_wed': False,
            'b2b_order_thu': False,
            'b2b_order_fri': False,
            'b2b_order_sat': False,
            'b2b_order_sun': False,
        })
        cls.website_distribucion = cls.env['website'].create({
            'name': 'Distribución EntreDos',
            'company_id': cls.company.id,
            'b2b_order_schedule_active': True,
            'b2b_order_mon': False,
            'b2b_order_tue': False,
            'b2b_order_wed': True,
            'b2b_order_thu': True,
            'b2b_order_fri': False,
            'b2b_order_sat': False,
            'b2b_order_sun': False,
        })

        cls.product_alfajor = cls.env['product.template'].create({
            'name': 'Alfajor Premium Chocolate Especial',
            'list_price': 1500.0,
            'type': 'consu',
        })

        # Regla de límite para Franquicias: máx 30 unidades
        cls.limit_franquicias = cls.env['b2b.product.order.limit'].create({
            'product_tmpl_id': cls.product_alfajor.id,
            'website_id': cls.website_franquicias.id,
            'max_qty': 30.0,
        })

        # Regla de límite para Distribución: máx 150 unidades
        cls.limit_distribucion = cls.env['b2b.product.order.limit'].create({
            'product_tmpl_id': cls.product_alfajor.id,
            'website_id': cls.website_distribucion.id,
            'max_qty': 150.0,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Franquicia Test Mendoza',
            'company_id': cls.company.id,
        })

    def test_01_allowed_days_computation(self):
        """Verifica el cálculo de días permitidos y la descripción formateada."""
        self.assertIn('Lunes', self.website_franquicias.b2b_allowed_days_display)
        self.assertIn('Martes', self.website_franquicias.b2b_allowed_days_display)

        # 2026-09-07 es Lunes
        lunes = datetime(2026, 9, 7, 12, 0, 0)
        # 2026-09-08 es Martes
        martes = datetime(2026, 9, 8, 12, 0, 0)
        # 2026-09-09 es Miércoles
        miercoles = datetime(2026, 9, 9, 12, 0, 0)
        # 2026-09-13 es Domingo
        domingo = datetime(2026, 9, 13, 12, 0, 0)

        self.assertTrue(self.website_franquicias.is_b2b_order_day_allowed(lunes))
        self.assertTrue(self.website_franquicias.is_b2b_order_day_allowed(martes))
        self.assertFalse(self.website_franquicias.is_b2b_order_day_allowed(miercoles))
        self.assertFalse(self.website_franquicias.is_b2b_order_day_allowed(domingo))

        # Distribución opera Miércoles y Jueves
        self.assertFalse(self.website_distribucion.is_b2b_order_day_allowed(lunes))
        self.assertTrue(self.website_distribucion.is_b2b_order_day_allowed(miercoles))

    def test_02_max_qty_capping(self):
        """Verifica que la cantidad se acote al tope máximo según el canal web del pedido."""
        order_franq = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
        })
        order_dist = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_distribucion.id,
            'company_id': self.company.id,
        })

        variant_id = self.product_alfajor.product_variant_id.id
        uom_id = self.product_alfajor.uom_id.id

        # Pedir 50 unidades en Franquicias (tope es 30) -> debe acotar a 30 con aviso
        capped_qty, warning = order_franq._verify_updated_quantity(
            None, variant_id, 50.0, uom_id
        )
        self.assertEqual(capped_qty, 30.0)
        self.assertTrue(warning)
        self.assertIn('30', warning)

        # Pedir 20 unidades en Franquicias (dentro del tope de 30) -> pasa sin alterar
        ok_qty, warning_ok = order_franq._verify_updated_quantity(
            None, variant_id, 20.0, uom_id
        )
        self.assertEqual(ok_qty, 20.0)
        self.assertFalse(warning_ok)

        # Pedir 50 unidades en Distribución (tope es 150) -> pasa sin alterar
        dist_qty, dist_warning = order_dist._verify_updated_quantity(
            None, variant_id, 50.0, uom_id
        )
        self.assertEqual(dist_qty, 50.0)
        self.assertFalse(dist_warning)

        # Pedir 200 unidades en Distribución (tope es 150) -> debe acotar a 150
        dist_capped, dist_capped_warning = order_dist._verify_updated_quantity(
            None, variant_id, 200.0, uom_id
        )
        self.assertEqual(dist_capped, 150.0)
        self.assertTrue(dist_capped_warning)
        self.assertIn('150', dist_capped_warning)

    def test_03_cart_add_blocked_when_day_closed(self):
        """Verifica que no se permita agregar productos al carrito si el día está cerrado."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
        })

        # Desactivar todos los días
        self.website_franquicias.write({
            'b2b_order_mon': False,
            'b2b_order_tue': False,
            'b2b_order_wed': False,
            'b2b_order_thu': False,
            'b2b_order_fri': False,
            'b2b_order_sat': False,
            'b2b_order_sun': False,
        })

        with self.assertRaises(UserError):
            order._cart_add(self.product_alfajor.product_variant_id.id, 5.0)
