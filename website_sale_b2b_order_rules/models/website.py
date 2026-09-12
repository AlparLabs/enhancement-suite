# -*- coding: utf-8 -*-
import pytz
from datetime import datetime
from odoo import api, fields, models, _


class Website(models.Model):
    _inherit = 'website'

    b2b_order_schedule_active = fields.Boolean(
        string="Restringir Días y Horarios de Pedido B2B",
        default=False,
        help="Si está activo, solo se permitirá realizar y armar pedidos en las franjas horarias configuradas."
    )
    b2b_schedule_ids = fields.One2many(
        'website.b2b.order.schedule',
        'website_id',
        string="Franjas Horarias de Pedidos B2B"
    )
    b2b_allowed_days_display = fields.Char(
        string="Horarios Habilitados",
        compute='_compute_b2b_allowed_days_display',
        help="Texto descriptivo de las franjas horarias en las que se reciben pedidos en este canal."
    )
    b2b_min_order_amount = fields.Monetary(
        string="Monto Mínimo de Pedido B2B",
        currency_field='currency_id',
        default=0.0,
        help="Monto total mínimo requerido para procesar pedidos en este canal. Ingrese 0 para no exigir monto mínimo."
    )


    @api.depends('b2b_schedule_ids', 'b2b_schedule_ids.day_of_week',
                 'b2b_schedule_ids.hour_from', 'b2b_schedule_ids.hour_to')
    def _compute_b2b_allowed_days_display(self):
        day_labels = {
            '0': _("Lunes"),
            '1': _("Martes"),
            '2': _("Miércoles"),
            '3': _("Jueves"),
            '4': _("Viernes"),
            '5': _("Sábado"),
            '6': _("Domingo"),
        }
        for website in self:
            if not website.b2b_schedule_ids:
                website.b2b_allowed_days_display = _("Ninguno (Cerrado)")
                continue

            lines_desc = []
            for s in website.b2b_schedule_ids.sorted(key=lambda r: (int(r.day_of_week), r.hour_from)):
                day_name = day_labels.get(s.day_of_week, s.day_of_week)
                h_from_int = int(s.hour_from)
                m_from_int = int(round((s.hour_from - h_from_int) * 60))
                h_to_int = int(s.hour_to)
                m_to_int = int(round((s.hour_to - h_to_int) * 60))
                time_str = f"{h_from_int:02d}:{m_from_int:02d} a {h_to_int:02d}:{m_to_int:02d} hs"
                lines_desc.append(f"{day_name} ({time_str})")

            website.b2b_allowed_days_display = ", ".join(lines_desc)

    def is_b2b_order_day_allowed(self, target_datetime=None):
        """
        Determina si el momento actual (o la fecha/hora dada) en la zona horaria del sitio web
        se encuentra dentro de alguna franja horaria habilitada para pedidos.
        """
        self.ensure_one()
        if not self.b2b_order_schedule_active:
            return True

        if not self.b2b_schedule_ids:
            return False

        tz_name = self.company_id.partner_id.tz or self.env.user.tz or 'America/Argentina/Buenos_Aires'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone('UTC')

        if target_datetime:
            if target_datetime.tzinfo is None:
                dt = pytz.utc.localize(target_datetime).astimezone(tz)
            else:
                dt = target_datetime.astimezone(tz)
        else:
            dt = datetime.now(tz)

        weekday = str(dt.weekday())  # '0'..'6'
        current_hour = dt.hour + (dt.minute / 60.0) + (dt.second / 3600.0)

        # Buscar si alguna franja de hoy cubre la hora actual
        matching_schedules = self.b2b_schedule_ids.filtered(
            lambda s: s.day_of_week == weekday and s.hour_from <= current_hour <= s.hour_to
        )
        return bool(matching_schedules)
