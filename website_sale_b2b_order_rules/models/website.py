# -*- coding: utf-8 -*-
import pytz
from datetime import datetime
from odoo import api, fields, models, _


class Website(models.Model):
    _inherit = 'website'

    b2b_order_schedule_active = fields.Boolean(
        string="Restringir Días de Pedido B2B",
        default=False,
        help="Si está activo, solo se permitirá realizar y armar pedidos en los días de la semana seleccionados."
    )
    b2b_order_mon = fields.Boolean(string="Lunes", default=True)
    b2b_order_tue = fields.Boolean(string="Martes", default=True)
    b2b_order_wed = fields.Boolean(string="Miércoles", default=True)
    b2b_order_thu = fields.Boolean(string="Jueves", default=True)
    b2b_order_fri = fields.Boolean(string="Viernes", default=True)
    b2b_order_sat = fields.Boolean(string="Sábado", default=False)
    b2b_order_sun = fields.Boolean(string="Domingo", default=False)

    b2b_allowed_days_display = fields.Char(
        string="Días Habilitados",
        compute='_compute_b2b_allowed_days_display',
        help="Texto descriptivo de los días de la semana en los que se reciben pedidos en este canal."
    )

    @api.depends(
        'b2b_order_mon', 'b2b_order_tue', 'b2b_order_wed', 'b2b_order_thu',
        'b2b_order_fri', 'b2b_order_sat', 'b2b_order_sun'
    )
    def _compute_b2b_allowed_days_display(self):
        day_names = [
            ('b2b_order_mon', _("Lunes")),
            ('b2b_order_tue', _("Martes")),
            ('b2b_order_wed', _("Miércoles")),
            ('b2b_order_thu', _("Jueves")),
            ('b2b_order_fri', _("Viernes")),
            ('b2b_order_sat', _("Sábado")),
            ('b2b_order_sun', _("Domingo")),
        ]
        for website in self:
            active_days = [name for field_name, name in day_names if website[field_name]]
            if len(active_days) == 7:
                website.b2b_allowed_days_display = _("Todos los días")
            elif len(active_days) > 1:
                website.b2b_allowed_days_display = f"{', '.join(active_days[:-1])} y {active_days[-1]}"
            elif active_days:
                website.b2b_allowed_days_display = active_days[0]
            else:
                website.b2b_allowed_days_display = _("Ninguno (Cerrado)")

    def is_b2b_order_day_allowed(self, target_datetime=None):
        """
        Determina si el día actual (o la fecha dada) en la zona horaria del sitio web
        se encuentra habilitado para la recepción de pedidos.
        """
        self.ensure_one()
        if not self.b2b_order_schedule_active:
            return True

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

        weekday = dt.weekday()  # 0=Monday, ..., 6=Sunday
        days_map = {
            0: self.b2b_order_mon,
            1: self.b2b_order_tue,
            2: self.b2b_order_wed,
            3: self.b2b_order_thu,
            4: self.b2b_order_fri,
            5: self.b2b_order_sat,
            6: self.b2b_order_sun,
        }
        return bool(days_map.get(weekday, False))
