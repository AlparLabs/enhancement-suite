# -*- coding: utf-8 -*-
from datetime import datetime, time
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    b2b_requested_delivery_date = fields.Date(
        string="Fecha de Entrega Solicitada",
        copy=False,
        help="Fecha programada por el cliente para la recepción del pedido en su local o depósito."
    )
    b2b_delivery_shift = fields.Selection(
        selection=[
            ('morning', 'Turno Mañana (08:00 a 13:00)'),
            ('afternoon', 'Turno Tarde (13:00 a 18:00)'),
            ('any', 'Horario Habitual / Todo el día'),
        ],
        string="Turno de Recepción Solicitado",
        default='morning',
        copy=False,
        help="Franja horaria preferida para la descarga."
    )
    b2b_delivery_notes = fields.Text(
        string="Instrucciones Especiales de Entrega",
        copy=False,
        help="Aclaraciones sobre descarga, acceso de camiones o contacto en destino."
    )

    def _sync_b2b_commitment_date(self):
        """
        Sincroniza el campo nativo commitment_date en base a la fecha y turno seleccionados,
        para que los albaranes de entrega de stock (stock.picking) hereden la fecha de despacho.
        """
        for order in self:
            if not order.b2b_requested_delivery_date:
                continue

            tz_name = (
                (order.website_id and order.website_id.company_id.partner_id.tz)
                or order.company_id.partner_id.tz
                or self.env.user.tz
                or 'America/Argentina/Buenos_Aires'
            )
            try:
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = pytz.timezone('America/Argentina/Buenos_Aires')

            hour_map = {
                'morning': time(10, 0),
                'afternoon': time(15, 0),
                'any': time(12, 0),
            }
            shift_time = hour_map.get(order.b2b_delivery_shift or 'morning', time(10, 0))
            local_dt = tz.localize(datetime.combine(order.b2b_requested_delivery_date, shift_time))
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            order.commitment_date = utc_dt

    def set_b2b_delivery_schedule(self, delivery_date, delivery_shift='morning', delivery_notes=None):
        """
        Asigna y valida la fecha y turno de entrega programada.
        """
        self.ensure_one()
        website = self.website_id
        if isinstance(delivery_date, str):
            delivery_date = fields.Date.from_string(delivery_date)

        if website and website.b2b_delivery_schedule_active and delivery_date:
            earliest = website._get_b2b_earliest_delivery_date()
            if delivery_date < earliest:
                raise UserError(_(
                    "La fecha de entrega seleccionada (%(selected)s) no cumple con el tiempo mínimo de "
                    "elaboración y preparación. La fecha más próxima habilitada es %(earliest)s.",
                    selected=fields.Date.to_string(delivery_date),
                    earliest=fields.Date.to_string(earliest)
                ))

        vals = {
            'b2b_requested_delivery_date': delivery_date,
            'b2b_delivery_shift': delivery_shift or 'morning',
        }
        if delivery_notes is not None:
            vals['b2b_delivery_notes'] = delivery_notes

        self.write(vals)
        self._sync_b2b_commitment_date()
        return True
