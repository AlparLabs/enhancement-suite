# -*- coding: utf-8 -*-
from datetime import datetime, date
import pytz
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestB2BDeliverySchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.tz = pytz.timezone('America/Argentina/Buenos_Aires')
        cls.company.partner_id.tz = 'America/Argentina/Buenos_Aires'

        cls.website = cls.env['website'].create({
            'name': 'Franquicias EntreDos',
            'company_id': cls.company.id,
            'b2b_delivery_schedule_active': True,
            'b2b_delivery_lead_days': 2,
            'b2b_delivery_cutoff_hour': 13.0,
            'b2b_allow_saturday_delivery': False,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Franquicia Test Mendoza',
            'company_id': cls.company.id,
        })

    def test_01_earliest_delivery_date_calculation(self):
        """Verifica el cálculo de días hábiles, saltando fines de semana y considerando la hora de corte."""
        # 2026-09-07 fue Lunes
        # Caso A: Lunes a las 10:00 hs (antes de corte 13:00) -> 2 días hábiles -> Miércoles 09/09
        lunes_morning = self.tz.localize(datetime(2026, 9, 7, 10, 0, 0))
        earliest_a = self.website._get_b2b_earliest_delivery_date(from_datetime=lunes_morning)
        self.assertEqual(earliest_a, date(2026, 9, 9))

        # Caso B: Lunes a las 14:00 hs (post corte 13:00) -> 3 días hábiles (2 + 1) -> Jueves 10/09
        lunes_afternoon = self.tz.localize(datetime(2026, 9, 7, 14, 0, 0))
        earliest_b = self.website._get_b2b_earliest_delivery_date(from_datetime=lunes_afternoon)
        self.assertEqual(earliest_b, date(2026, 9, 10))

        # Caso C: Jueves 10/09 a las 15:00 hs (post corte 13:00)
        # Lead time = 2 + 1 = 3 días hábiles:
        # Día 1: Viernes 11/09
        # Sábado y Domingo se saltan
        # Día 2: Lunes 14/09
        # Día 3: Martes 15/09
        jueves_afternoon = self.tz.localize(datetime(2026, 9, 10, 15, 0, 0))
        earliest_c = self.website._get_b2b_earliest_delivery_date(from_datetime=jueves_afternoon)
        self.assertEqual(earliest_c, date(2026, 9, 15))

        # Caso D: Habilitando sábados
        self.website.b2b_allow_saturday_delivery = True
        # Jueves 15:00 hs (3 días hábiles contando sábados):
        # Día 1: Viernes 11/09
        # Día 2: Sábado 12/09
        # Domingo se salta
        # Día 3: Lunes 14/09
        earliest_d = self.website._get_b2b_earliest_delivery_date(from_datetime=jueves_afternoon)
        self.assertEqual(earliest_d, date(2026, 9, 14))

    def test_02_sale_order_schedule_persistence_and_commitment_sync(self):
        """Verifica la persistencia de fecha/turno y la sincronización con commitment_date en UTC."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website.id,
            'company_id': self.company.id,
        })

        target_date = date(2026, 9, 25)
        order.set_b2b_delivery_schedule(target_date, delivery_shift='morning', delivery_notes='Timbre 4B')

        self.assertEqual(order.b2b_requested_delivery_date, target_date)
        self.assertEqual(order.b2b_delivery_shift, 'morning')
        self.assertEqual(order.b2b_delivery_notes, 'Timbre 4B')
        self.assertTrue(order.commitment_date)

        # En horario de Argentina (UTC-3), las 10:00 hs corresponden a las 13:00 UTC
        self.assertEqual(order.commitment_date.hour, 13)
        self.assertEqual(order.commitment_date.minute, 0)

        # Cambiar a turno tarde (15:00 hs local -> 18:00 UTC)
        order.set_b2b_delivery_schedule(target_date, delivery_shift='afternoon')
        self.assertEqual(order.b2b_delivery_shift, 'afternoon')
        self.assertEqual(order.commitment_date.hour, 18)

    def test_03_delivery_date_validation_earliest(self):
        """Verifica que se impida seleccionar una fecha anterior a la más temprana permitida."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website.id,
            'company_id': self.company.id,
        })

        # Fecha de ayer (claramente inválida)
        past_date = date(2020, 1, 1)
        with self.assertRaises(UserError):
            order.set_b2b_delivery_schedule(past_date, delivery_shift='morning')
