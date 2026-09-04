# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CHANNEL_NAME = "alpar_queue_channel"


class QueueTicket(models.Model):
    _name = "queue.ticket"
    _description = "Turno de Atenci?n"
    _order = "id desc"
    _rec_name = "number"

    number = fields.Char(
        string="N?mero de Turno",
        required=True,
        copy=False,
        index=True,
        help="C?digo del turno visible para el cliente (ej. C-001, V-012)",
    )
    sequence_number = fields.Integer(string="Secuencia Diaria", default=1, copy=False)
    queue_type = fields.Selection(
        [
            ("caja", "Caja / POS"),
            ("ventas", "Ventas / Asesor?a"),
        ],
        string="Tipo de Turno",
        required=True,
        default="caja",
        index=True,
    )
    state = fields.Selection(
        [
            ("waiting", "En Espera"),
            ("called", "Llamando"),
            ("done", "Atendido"),
            ("cancel", "Ausente / Cancelado"),
        ],
        string="Estado",
        default="waiting",
        required=True,
        index=True,
    )

    # Datos del cliente
    partner_id = fields.Many2one("res.partner", string="Cliente")
    customer_name = fields.Char(string="Nombre Cliente")
    customer_vat = fields.Char(string="DNI / CUIT", index=True)
    customer_phone = fields.Char(string="Tel?fono / Celular")

    # Datos de atenci?n
    station = fields.Char(string="Puesto / Caja", copy=False, help="Ej: Caja 1, Puesto 2")
    user_id = fields.Many2one(
        "res.users",
        string="Atendido por",
        copy=False,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compa??a",
        default=lambda self: self.env.company,
        required=True,
    )

    # Tiempos y m?tricas
    call_date = fields.Datetime(string="Hora de Llamado", readonly=True, copy=False)
    done_date = fields.Datetime(string="Hora de Finalizaci?n", readonly=True, copy=False)
    waiting_time_minutes = fields.Float(
        string="Tiempo de Espera (min)",
        compute="_compute_times",
        store=True,
    )
    service_time_minutes = fields.Float(
        string="Tiempo de Atenci?n (min)",
        compute="_compute_times",
        store=True,
    )
    note = fields.Text(string="Notas")

    @api.depends("create_date", "call_date", "done_date")
    def _compute_times(self):
        for ticket in self:
            if ticket.create_date and ticket.call_date:
                diff = ticket.call_date - ticket.create_date
                ticket.waiting_time_minutes = round(diff.total_seconds() / 60.0, 1)
            else:
                ticket.waiting_time_minutes = 0.0

            if ticket.call_date and ticket.done_date:
                diff = ticket.done_date - ticket.call_date
                ticket.service_time_minutes = round(diff.total_seconds() / 60.0, 1)
            else:
                ticket.service_time_minutes = 0.0

    def action_call(self, station=None):
        for ticket in self:
            vals = {
                "state": "called",
                "call_date": fields.Datetime.now(),
                "user_id": self.env.user.id,
            }
            if station:
                vals["station"] = station
            ticket.write(vals)
        self._notify_display(last_ticket=self[:1])
        return True

    def action_done(self):
        for ticket in self:
            ticket.write({
                "state": "done",
                "done_date": fields.Datetime.now(),
            })
        self._notify_display()
        return True

    def action_cancel(self):
        for ticket in self:
            ticket.write({
                "state": "cancel",
                "done_date": fields.Datetime.now(),
            })
        self._notify_display()
        return True

    def action_reset_waiting(self):
        for ticket in self:
            ticket.write({
                "state": "waiting",
                "call_date": False,
                "done_date": False,
                "station": False,
            })
        self._notify_display()
        return True

    def _notify_display(self, last_ticket=None):
        try:
            channel = f"{CHANNEL_NAME}_{self.env.company.id}"
            data = self.get_display_data(last_ticket=last_ticket)
            self.env["bus.bus"]._sendone(channel, "alpar_queue/update", data)
            _logger.info("Notificaci?n de turnos enviada a bus canal %s", channel)
        except Exception as e:
            _logger.warning("No se pudo emitir evento bus para turnos: %s", str(e))

    @api.model
    def create_from_kiosk(self, vals):
        """Crea un turno desde la Terminal Kiosco Android."""
        company = self.env.company
        queue_type = vals.get("queue_type", "caja")
        customer_name = vals.get("customer_name") or ""
        customer_vat = vals.get("customer_vat") or ""
        customer_phone = vals.get("customer_phone") or ""

        # Buscar cliente existente por DNI/CUIT o tel?fono
        partner = False
        if customer_vat:
            partner = self.env["res.partner"].search([
                ("vat", "=", customer_vat),
                "|", ("company_id", "=", False), ("company_id", "=", company.id)
            ], limit=1)
        if not partner and customer_phone:
            partner = self.env["res.partner"].search([
                "|", ("phone", "=", customer_phone), ("mobile", "=", customer_phone),
                "|", ("company_id", "=", False), ("company_id", "=", company.id)
            ], limit=1)

        # Si encontramos partner y no ven?a nombre expl?cito, usamos el de Odoo
        if partner and not customer_name:
            customer_name = partner.name

        # C?lculo de correlativo diario
        today_start = datetime.combine(fields.Date.context_today(self), time.min)
        domain = [
            ("queue_type", "=", queue_type),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ]
        count_today = self.search_count(domain)
        sequence_number = count_today + 1

        prefix = "C" if queue_type == "caja" else "V"
        number = f"{prefix}-{sequence_number:03d}"

        ticket = self.create({
            "number": number,
            "sequence_number": sequence_number,
            "queue_type": queue_type,
            "state": "waiting",
            "partner_id": partner.id if partner else False,
            "customer_name": customer_name,
            "customer_vat": customer_vat,
            "customer_phone": customer_phone,
            "company_id": company.id,
        })

        # Turnos en espera delante de este
        waiting_ahead = self.search_count([
            ("queue_type", "=", queue_type),
            ("state", "=", "waiting"),
            ("company_id", "=", company.id),
            ("id", "<", ticket.id),
            ("create_date", ">=", today_start),
        ])

        ticket._notify_display()

        return {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "queue_type": ticket.queue_type,
            "customer_name": ticket.customer_name or "",
            "waiting_ahead": waiting_ahead,
            "create_date": fields.Datetime.to_string(ticket.create_date),
        }

    @api.model
    def call_next(self, queue_type="caja", station="Caja"):
        """Llama al siguiente turno en espera para la cola dada."""
        company = self.env.company
        today_start = datetime.combine(fields.Date.context_today(self), time.min)

        ticket = self.search([
            ("queue_type", "=", queue_type),
            ("state", "=", "waiting"),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ], order="id asc", limit=1)

        if not ticket:
            return False

        ticket.action_call(station=station)

        return {
            "id": ticket.id,
            "number": ticket.number,
            "partner_id": ticket.partner_id.id if ticket.partner_id else False,
            "partner_name": ticket.partner_id.name or ticket.customer_name or "",
            "station": ticket.station or station,
            "queue_type": ticket.queue_type,
            "state": ticket.state,
        }

    @api.model
    def get_queue_status(self):
        """Devuelve conteos r?pidos de turnos en espera para POS y Ventas."""
        company = self.env.company
        today_start = datetime.combine(fields.Date.context_today(self), time.min)

        waiting_caja = self.search_count([
            ("queue_type", "=", "caja"),
            ("state", "=", "waiting"),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ])
        waiting_ventas = self.search_count([
            ("queue_type", "=", "ventas"),
            ("state", "=", "waiting"),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ])

        return {
            "waiting_caja": waiting_caja,
            "waiting_ventas": waiting_ventas,
        }

    @api.model
    def get_display_data(self, last_ticket=None):
        """Datos completos estructurados para la pantalla de TV (sala de espera)."""
        company = self.env.company
        today_start = datetime.combine(fields.Date.context_today(self), time.min)

        # ?ltimos turnos llamados o en atenci?n (m?ximo 5 de cada tipo para la pantalla)
        called_caja_records = self.search([
            ("queue_type", "=", "caja"),
            ("state", "=", "called"),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ], order="call_date desc, id desc", limit=4)

        called_ventas_records = self.search([
            ("queue_type", "=", "ventas"),
            ("state", "=", "called"),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ], order="call_date desc, id desc", limit=4)

        def _format_ticket(t):
            return {
                "id": t.id,
                "number": t.number,
                "station": t.station or ("Caja" if t.queue_type == "caja" else "Puesto"),
                "customer_name": t.customer_name or (t.partner_id.name if t.partner_id else ""),
                "queue_type": t.queue_type,
                "call_time": fields.Datetime.to_string(t.call_date) if t.call_date else "",
            }

        last_called_data = False
        if last_ticket:
            last_called_data = _format_ticket(last_ticket)
        else:
            # Buscar el m?s recientemente llamado en general
            recent = self.search([
                ("state", "=", "called"),
                ("company_id", "=", company.id),
                ("create_date", ">=", today_start),
            ], order="call_date desc, id desc", limit=1)
            if recent:
                last_called_data = _format_ticket(recent)

        status = self.get_queue_status()

        return {
            "company_name": company.name,
            "channel": f"{CHANNEL_NAME}_{company.id}",
            "last_called": last_called_data,
            "called_caja": [_format_ticket(t) for t in called_caja_records],
            "called_ventas": [_format_ticket(t) for t in called_ventas_records],
            "waiting_caja": status["waiting_caja"],
            "waiting_ventas": status["waiting_ventas"],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
