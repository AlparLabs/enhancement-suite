# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import pytz
from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    b2b_delivery_schedule_active = fields.Boolean(
        string="Activar Programación de Entregas B2B",
        default=True,
        help="Permite a franquiciados y distribuidores elegir fecha y turno de entrega en el checkout."
    )
    b2b_delivery_lead_days = fields.Integer(
        string="Días Mínimos de Anticipación (Lead Time)",
        default=2,
        help="Días hábiles requeridos de elaboración y preparación antes del despacho."
    )
    b2b_delivery_cutoff_hour = fields.Float(
        string="Hora de Corte Diaria",
        default=13.0,
        help="Pedidos recibidos después de esta hora suman 1 día hábil adicional de margen logístico."
    )
    b2b_allow_saturday_delivery = fields.Boolean(
        string="Permitir Entregas los Sábados",
        default=False,
        help="Habilita los días sábados como fecha de entrega posible."
    )

    def _get_b2b_earliest_delivery_date(self, from_datetime=None):
        """
        Calcula la fecha de entrega más temprana disponible en base al lead time,
        la hora de corte diaria y los días no laborables (domingos y sábados según config).
        """
        self.ensure_one()
        tz_name = self.company_id.partner_id.tz or self.env.user.tz or 'America/Argentina/Buenos_Aires'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone('America/Argentina/Buenos_Aires')

        now = from_datetime or datetime.now(tz)
        if now.tzinfo is None:
            now = tz.localize(now)
        else:
            now = now.astimezone(tz)

        lead_days = self.b2b_delivery_lead_days if self.b2b_delivery_lead_days > 0 else 1

        # Si el pedido se realiza luego de la hora de corte, se computa a partir del siguiente día
        current_decimal_hour = now.hour + now.minute / 60.0
        cutoff = self.b2b_delivery_cutoff_hour if self.b2b_delivery_cutoff_hour > 0 else 13.0
        if current_decimal_hour >= cutoff:
            lead_days += 1

        cur_date = now.date()
        added_days = 0
        while added_days < lead_days:
            cur_date += timedelta(days=1)
            # 5 = Sábado, 6 = Domingo
            if cur_date.weekday() == 6:
                continue
            if cur_date.weekday() == 5 and not self.b2b_allow_saturday_delivery:
                continue
            added_days += 1

        return cur_date
