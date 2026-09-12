# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import fields
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
        })
        # Configurar franjas: Lunes 08:00 a 18:00, Viernes 08:00 a 13:00
        cls.env['website.b2b.order.schedule'].create([
            {
                'website_id': cls.website_franquicias.id,
                'day_of_week': '0',  # Lunes
                'hour_from': 8.0,
                'hour_to': 18.0,
            },
            {
                'website_id': cls.website_franquicias.id,
                'day_of_week': '4',  # Viernes
                'hour_from': 8.0,
                'hour_to': 13.0,  # Corte 13:00
            }
        ])

        cls.website_distribucion = cls.env['website'].create({
            'name': 'Distribución EntreDos',
            'company_id': cls.company.id,
            'b2b_order_schedule_active': True,
        })
        # Distribución: Miércoles 08:00 a 20:00
        cls.env['website.b2b.order.schedule'].create({
            'website_id': cls.website_distribucion.id,
            'day_of_week': '2',  # Miércoles
            'hour_from': 8.0,
            'hour_to': 20.0,
        })

        cls.product_alfajor = cls.env['product.template'].create({
            'name': 'Alfajor Premium Chocolate Especial',
            'list_price': 1500.0,
            'type': 'consu',
        })

        cls.product_libre = cls.env['product.template'].create({
            'name': 'Producto Sin Límites',
            'list_price': 1000.0,
            'type': 'consu',
        })

        # Regla permanente general para Franquicias: máx 50 unidades
        cls.limit_general = cls.env['b2b.product.order.limit'].create({
            'name': 'General Permanente',
            'product_tmpl_id': cls.product_alfajor.id,
            'website_id': cls.website_franquicias.id,
            'max_qty': 50.0,
        })

        # Regla estacional (vigente hoy): máx 15 unidades
        today = fields.Date.today()
        cls.limit_temporada = cls.env['b2b.product.order.limit'].create({
            'name': 'Especial Temporada',
            'product_tmpl_id': cls.product_alfajor.id,
            'website_id': cls.website_franquicias.id,
            'date_from': today - timedelta(days=2),
            'date_to': today + timedelta(days=2),
            'max_qty': 15.0,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Franquicia Test Mendoza',
            'company_id': cls.company.id,
        })

    def test_01_allowed_schedule_and_cutoff_hours(self):
        """Verifica el cálculo de días y horarios de corte (ej. Viernes hasta las 13:00)."""
        self.assertIn('Lunes', self.website_franquicias.b2b_allowed_days_display)
        self.assertIn('Viernes', self.website_franquicias.b2b_allowed_days_display)
        self.assertIn('13:00', self.website_franquicias.b2b_allowed_days_display)

        # 2026-09-11 fue Viernes
        viernes_ok = datetime(2026, 9, 11, 11, 30, 0)      # 11:30 hs -> Abierto
        viernes_corte = datetime(2026, 9, 11, 13, 15, 0)   # 13:15 hs -> Pasó el corte de 13:00 (Cerrado)
        viernes_temprano = datetime(2026, 9, 11, 7, 0, 0)  # 07:00 hs -> Antes de las 08:00 (Cerrado)

        # 2026-09-07 fue Lunes
        lunes_ok = datetime(2026, 9, 7, 10, 0, 0)          # 10:00 hs -> Abierto (8 a 18)
        lunes_tarde = datetime(2026, 9, 7, 19, 0, 0)       # 19:00 hs -> Cerrado

        # 2026-09-09 fue Miércoles
        miercoles_franq = datetime(2026, 9, 9, 10, 0, 0)   # Miércoles cerrado en Franquicias

        self.assertTrue(self.website_franquicias.is_b2b_order_day_allowed(viernes_ok))
        self.assertFalse(self.website_franquicias.is_b2b_order_day_allowed(viernes_corte))
        self.assertFalse(self.website_franquicias.is_b2b_order_day_allowed(viernes_temprano))

        self.assertTrue(self.website_franquicias.is_b2b_order_day_allowed(lunes_ok))
        self.assertFalse(self.website_franquicias.is_b2b_order_day_allowed(lunes_tarde))
        self.assertFalse(self.website_franquicias.is_b2b_order_day_allowed(miercoles_franq))

        # En Distribución, Miércoles sí está abierto
        self.assertTrue(self.website_distribucion.is_b2b_order_day_allowed(miercoles_franq))

    def test_02_seasonal_and_weekly_limits_priority(self):
        """Verifica que la regla de temporada activa tenga prioridad sobre la regla general, y que productos sin reglas estén liberados."""
        today = fields.Date.today()
        active_limit = self.product_alfajor._get_b2b_order_limit_for_website(self.website_franquicias, order_date=today)
        self.assertEqual(active_limit.id, self.limit_temporada.id)
        self.assertEqual(active_limit.max_qty, 15.0)

        # Fecha fuera de temporada (ej. dentro de 30 días): rige la regla general permanente (50)
        future_date = today + timedelta(days=30)
        future_limit = self.product_alfajor._get_b2b_order_limit_for_website(self.website_franquicias, order_date=future_date)
        self.assertEqual(future_limit.id, self.limit_general.id)
        self.assertEqual(future_limit.max_qty, 50.0)

        # Producto sin reglas: retorna vacío (sin límites)
        limit_libre = self.product_libre._get_b2b_order_limit_for_website(self.website_franquicias)
        self.assertFalse(limit_libre)

        # En el pedido, el producto libre permite 500 unidades sin acotar
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
        })
        libre_qty, warning = order._verify_updated_quantity(
            None, self.product_libre.product_variant_id.id, 500.0, self.product_libre.uom_id.id
        )
        self.assertEqual(libre_qty, 500.0)
        self.assertFalse(warning)

    def test_03_cart_add_blocked_when_outside_schedule(self):
        """Verifica que se impida armar carrito si el canal se encuentra fuera de horario."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
        })

        # Eliminar las franjas horarias para simular canal completamente cerrado
        self.website_franquicias.b2b_schedule_ids.unlink()

        with self.assertRaises(UserError):
            order._cart_add(self.product_alfajor.product_variant_id.id, 5.0)

    def test_04_b2b_min_order_amount(self):
        """Verifica el cálculo de cumplimiento y saldo faltante de monto mínimo por canal."""
        self.website_franquicias.b2b_min_order_amount = 50000.0

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
        })
        # Inicialmente vacío: total 0 < 50000 -> is_unmet: True, missing_amount: 50000
        status = order._get_b2b_min_amount_status()
        self.assertTrue(status['is_unmet'])
        self.assertEqual(status['min_amount'], 50000.0)
        self.assertEqual(status['missing_amount'], 50000.0)

        # Agregar línea de 30000 (20 x 1500)
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_alfajor.product_variant_id.id,
            'product_uom_qty': 20.0,
            'price_unit': 1500.0,
        })
        status = order._get_b2b_min_amount_status()
        self.assertTrue(status['is_unmet'])
        self.assertEqual(status['current_amount'], 30000.0)
        self.assertEqual(status['missing_amount'], 20000.0)

        # Agregar otra línea superando los 50000 (30 x 1000 = 30000 adicionales -> total 60000)
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_libre.product_variant_id.id,
            'product_uom_qty': 30.0,
            'price_unit': 1000.0,
        })
        status = order._get_b2b_min_amount_status()
        self.assertFalse(status['is_unmet'])
        self.assertEqual(status['missing_amount'], 0.0)

    def test_05_reorder_workflow(self):
        """Verifica la lógica de repetición de pedidos respetando topes de canal."""
        # Crear pedido histórico
        past_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
            'state': 'sale',
        })
        self.env['sale.order.line'].create([
            {
                'order_id': past_order.id,
                'product_id': self.product_alfajor.product_variant_id.id,
                'product_uom_qty': 10.0,
                'price_unit': 1500.0,
            },
            {
                'order_id': past_order.id,
                'product_id': self.product_libre.product_variant_id.id,
                'product_uom_qty': 25.0,
                'price_unit': 1000.0,
            }
        ])

        # Crear nuevo carrito en ventana habilitada
        new_cart = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website_franquicias.id,
            'company_id': self.company.id,
        })
        # Simular adición de líneas del pedido previo
        for line in past_order.order_line:
            new_cart._cart_add(line.product_id.id, line.product_uom_qty)

        self.assertEqual(len(new_cart.order_line), 2)
        alfajor_line = new_cart.order_line.filtered(lambda l: l.product_id == self.product_alfajor.product_variant_id)
        libre_line = new_cart.order_line.filtered(lambda l: l.product_id == self.product_libre.product_variant_id)
        self.assertEqual(alfajor_line.product_uom_qty, 10.0)
        self.assertEqual(libre_line.product_uom_qty, 25.0)
