# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CHANNEL_NAME = "alpar_queue_channel"


class QueueTicket(models.Model):
    _name = "queue.ticket"
    _description = "Turno de Atención"
    _order = "id desc"
    _rec_name = "number"

    number = fields.Char(
        string="Número de Turno",
        required=True,
        copy=False,
        index=True,
        help="Código del turno visible para el cliente (ej. C-001, V-012)",
    )
    sequence_number = fields.Integer(string="Secuencia Diaria", default=1, copy=False)

    queue_type_id = fields.Many2one(
        "queue.ticket.type",
        string="Tipo de Turno",
        required=True,
        index=True,
        ondelete="restrict",
    )
    queue_type_code = fields.Char(
        related="queue_type_id.code",
        string="Código de Tipo",
        store=True,
        index=True,
    )
    queue_type = fields.Char(
        string="Tipo de Turno (Código)",
        compute="_compute_queue_type",
        inverse="_inverse_queue_type",
        search="_search_queue_type",
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
    customer_phone = fields.Char(string="Teléfono / Celular")

    # Datos de atención
    station = fields.Char(string="Puesto / Caja", copy=False, help="Ej: Caja 1, Puesto 2")
    user_id = fields.Many2one(
        "res.users",
        string="Atendido por",
        copy=False,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )

    # Tiempos y métricas
    call_date = fields.Datetime(string="Hora de Llamado", readonly=True, copy=False)
    done_date = fields.Datetime(string="Hora de Finalización", readonly=True, copy=False)
    waiting_time_minutes = fields.Float(
        string="Tiempo de Espera (min)",
        compute="_compute_times",
        store=True,
    )
    service_time_minutes = fields.Float(
        string="Tiempo de Atención (min)",
        compute="_compute_times",
        store=True,
    )
    note = fields.Text(string="Notas")

    @api.depends("queue_type_id")
    def _compute_queue_type(self):
        for ticket in self:
            ticket.queue_type = ticket.queue_type_id.code or ""

    def _inverse_queue_type(self):
        for ticket in self:
            if ticket.queue_type:
                q_type = self.env["queue.ticket.type"].search([
                    ("code", "=", ticket.queue_type),
                    "|", ("company_id", "=", False), ("company_id", "=", ticket.company_id.id or self.env.company.id)
                ], limit=1)
                if q_type:
                    ticket.queue_type_id = q_type.id

    def _search_queue_type(self, operator, value):
        return [("queue_type_id.code", operator, value)]

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
            _logger.info("Notificación de turnos enviada a bus canal %s", channel)
        except Exception as e:
            _logger.warning("No se pudo emitir evento bus para turnos: %s", str(e))

    @api.model
    def create_from_kiosk(self, vals):
        """Crea un turno desde la Terminal Kiosco Android con tipo dinámico."""
        company = self.env.company
        customer_name = vals.get("customer_name") or ""
        customer_vat = vals.get("customer_vat") or ""
        customer_phone = vals.get("customer_phone") or ""

        # Resolver el tipo de turno dinámico
        queue_type = False
        if vals.get("queue_type_id"):
            queue_type = self.env["queue.ticket.type"].browse(int(vals["queue_type_id"])).exists()
        elif vals.get("queue_type"):
            queue_type = self.env["queue.ticket.type"].search([
                ("code", "=", vals["queue_type"]),
                "|", ("company_id", "=", False), ("company_id", "=", company.id)
            ], limit=1)

        if not queue_type:
            # Fallback al primer tipo activo
            queue_type = self.env["queue.ticket.type"].search([
                ("active", "=", True),
                "|", ("company_id", "=", False), ("company_id", "=", company.id)
            ], order="sequence, id", limit=1)

        if not queue_type:
            raise UserError(_("No hay tipos de turnos configurados para esta compañía."))

        # Buscar cliente existente por DNI/CUIT o teléfono
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

        # Si encontramos partner y no venía nombre explícito, usamos el de Odoo
        if partner and not customer_name:
            customer_name = partner.name

        # Cálculo de correlativo diario
        today_start = datetime.combine(fields.Date.context_today(self), time.min)
        domain = [
            ("queue_type_id", "=", queue_type.id),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ]
        count_today = self.search_count(domain)
        sequence_number = count_today + 1

        prefix = queue_type.prefix or "T"
        number = f"{prefix}-{sequence_number:03d}"

        ticket = self.create({
            "number": number,
            "sequence_number": sequence_number,
            "queue_type_id": queue_type.id,
            "state": "waiting",
            "partner_id": partner.id if partner else False,
            "customer_name": customer_name,
            "customer_vat": customer_vat,
            "customer_phone": customer_phone,
            "company_id": company.id,
        })

        # Turnos en espera delante de este
        waiting_ahead = self.search_count([
            ("queue_type_id", "=", queue_type.id),
            ("state", "=", "waiting"),
            ("company_id", "=", company.id),
            ("id", "<", ticket.id),
            ("create_date", ">=", today_start),
        ])

        ticket._notify_display()

        return {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "queue_type_id": ticket.queue_type_id.id,
            "queue_type": ticket.queue_type_id.code,
            "queue_type_name": ticket.queue_type_id.name,
            "customer_name": ticket.customer_name or "",
            "waiting_ahead": waiting_ahead,
            "create_date": fields.Datetime.to_string(ticket.create_date),
        }

    @api.model
    def call_next(self, queue_type=None, station=None, queue_type_id=None):
        """Llama al siguiente turno en espera para la cola dada."""
        company = self.env.company
        today_start = datetime.combine(fields.Date.context_today(self), time.min)

        domain = [
            ("state", "=", "waiting"),
            ("company_id", "=", company.id),
            ("create_date", ">=", today_start),
        ]

        if queue_type_id:
            domain.append(("queue_type_id", "=", int(queue_type_id)))
        elif queue_type:
            domain.append(("queue_type_id.code", "=", queue_type))

        ticket = self.search(domain, order="id asc", limit=1)

        if not ticket:
            return False

        station_name = station or (ticket.queue_type_id.name or "Puesto")
        ticket.action_call(station=station_name)

        return {
            "id": ticket.id,
            "number": ticket.number,
            "partner_id": ticket.partner_id.id if ticket.partner_id else False,
            "partner_name": ticket.partner_id.name or ticket.customer_name or "",
            "station": ticket.station or station_name,
            "queue_type_id": ticket.queue_type_id.id,
            "queue_type": ticket.queue_type_id.code,
            "queue_type_name": ticket.queue_type_id.name,
            "state": ticket.state,
        }

    @api.model
    def get_queue_status(self, company_id=None):
        """Devuelve conteos de turnos en espera agrupados por tipos configurados."""
        if company_id:
            company = self.env["res.company"].browse(int(company_id)).exists() or self.env.company
        else:
            company = self.env.company

        today_start = datetime.combine(fields.Date.context_today(self), time.min)

        domain = [("active", "=", True)]
        if company:
            domain.append("|")
            domain.append(("company_id", "=", False))
            domain.append(("company_id", "=", company.id))

        types = self.env["queue.ticket.type"].search(domain, order="sequence, id")
        all_active = self.env["queue.ticket.type"].search([("active", "=", True)], order="sequence, id")
        if len(all_active) > len(types):
            types = all_active

        status = {}
        by_type = {}
        total_waiting = 0

        for t in types:
            ticket_domain = [
                ("queue_type_id", "=", t.id),
                ("state", "=", "waiting"),
                ("create_date", ">=", today_start),
            ]
            target_company_id = t.company_id.id if t.company_id else (company.id if company else False)
            if target_company_id:
                ticket_domain.append(("company_id", "=", target_company_id))

            cnt = self.search_count(ticket_domain)
            by_type[t.id] = {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "prefix": t.prefix,
                "waiting_count": cnt,
            }
            status[f"waiting_{t.code}"] = cnt
            total_waiting += cnt

        status["by_type"] = by_type
        status["total_waiting"] = total_waiting
        status["waiting_caja"] = status.get("waiting_caja", 0)
        status["waiting_ventas"] = status.get("waiting_ventas", 0)

        return status

    @api.model
    def get_display_data(self, last_ticket=None, company_id=None):
        """Datos estructurados para la pantalla de TV con categorías dinámicas."""
        if company_id:
            company = self.env["res.company"].browse(int(company_id)).exists() or self.env.company
        else:
            company = self.env.company

        today_start = datetime.combine(fields.Date.context_today(self), time.min)

        # Buscar tipos activos de la compañía o compartidos
        domain = [("active", "=", True)]
        if company:
            domain.append("|")
            domain.append(("company_id", "=", False))
            domain.append(("company_id", "=", company.id))

        types = self.env["queue.ticket.type"].search(domain, order="sequence, id")

        # Si solo encontró las predeterminadas (<= 2) pero hay más tipos activos en el sistema:
        all_active_types = self.env["queue.ticket.type"].search([("active", "=", True)], order="sequence, id")
        if len(all_active_types) > len(types):
            types = all_active_types

        def _format_ticket(t):
            call_time_str = ""
            if t.call_date:
                try:
                    call_time_str = fields.Datetime.context_timestamp(self, t.call_date).strftime("%H:%M")
                except Exception:
                    call_time_str = fields.Datetime.to_string(t.call_date)[11:16] if t.call_date else ""

            return {
                "id": t.id,
                "number": t.number,
                "station": t.station or (t.queue_type_id.name if t.queue_type_id else "Puesto"),
                "customer_name": t.customer_name or (t.partner_id.name if t.partner_id else ""),
                "queue_type_id": t.queue_type_id.id if t.queue_type_id else False,
                "queue_type": t.queue_type_id.code if t.queue_type_id else "",
                "queue_type_name": t.queue_type_id.name if t.queue_type_id else "",
                "queue_color": t.queue_type_id.color if (t.queue_type_id and t.queue_type_id.color) else "#2563eb",
                "queue_icon": t.queue_type_id.icon if (t.queue_type_id and t.queue_type_id.icon) else "fa-ticket",
                "call_time": call_time_str,
            }

        categories_data = []
        called_caja_list = []
        called_ventas_list = []
        waiting_summary = []

        for t in types:
            ticket_domain = [
                ("queue_type_id", "=", t.id),
                ("create_date", ">=", today_start),
            ]
            target_company_id = t.company_id.id if t.company_id else (company.id if company else False)
            if target_company_id:
                ticket_domain.append(("company_id", "=", target_company_id))

            called_records = self.search(
                ticket_domain + [("state", "in", ("called", "done"))],
                order="call_date desc, id desc",
                limit=4,
            )

            waiting_cnt = self.search_count(
                ticket_domain + [("state", "=", "waiting")]
            )

            formatted_called = [_format_ticket(rec) for rec in called_records]
            if t.code == "caja":
                called_caja_list = formatted_called
            elif t.code == "ventas":
                called_ventas_list = formatted_called

            type_color = t.color or "#2563eb"
            type_icon = t.icon or "fa-ticket"

            categories_data.append({
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "prefix": t.prefix,
                "color": type_color,
                "icon": type_icon,
                "waiting_count": waiting_cnt,
                "called_tickets": formatted_called,
            })

            waiting_summary.append({
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "prefix": t.prefix,
                "color": type_color,
                "icon": type_icon,
                "waiting_count": waiting_cnt,
            })

        # Últimos llamados unificados (hasta 8 tickets llamados hoy)
        recent_domain = [
            ("state", "in", ("called", "done")),
            ("create_date", ">=", today_start),
        ]
        if company:
            recent_domain.append(("company_id", "=", company.id))
        recent_called_records = self.search(recent_domain, order="call_date desc, id desc", limit=8)
        if not recent_called_records and company:
            # Fallback sin filtro de compañía
            recent_called_records = self.search([
                ("state", "in", ("called", "done")),
                ("create_date", ">=", today_start),
            ], order="call_date desc, id desc", limit=8)
        recent_called = [_format_ticket(rec) for rec in recent_called_records]

        # Último llamado principal
        last_called_data = False
        if last_ticket:
            last_called_data = _format_ticket(last_ticket)
        elif recent_called:
            last_called_data = recent_called[0]

        # Turnos en espera unificados (orden FIFO por id asc)
        waiting_domain = [
            ("state", "=", "waiting"),
            ("create_date", ">=", today_start),
        ]
        if company:
            waiting_domain.append(("company_id", "=", company.id))
        waiting_records = self.search(waiting_domain, order="id asc", limit=20)
        if not waiting_records and company:
            waiting_records = self.search([
                ("state", "=", "waiting"),
                ("create_date", ">=", today_start),
            ], order="id asc", limit=20)

        waiting_tickets = [
            {
                "id": w.id,
                "number": w.number,
                "customer_name": w.customer_name or (w.partner_id.name if w.partner_id else ""),
                "queue_type_id": w.queue_type_id.id if w.queue_type_id else False,
                "queue_type_name": w.queue_type_id.name if w.queue_type_id else "",
                "queue_color": w.queue_type_id.color if (w.queue_type_id and w.queue_type_id.color) else "#2563eb",
                "queue_icon": w.queue_type_id.icon if (w.queue_type_id and w.queue_type_id.icon) else "fa-ticket",
            }
            for w in waiting_records
        ]

        status = self.get_queue_status(company_id=company.id if company else None)

        return {
            "company_name": company.name if company else "",
            "company_id": company.id if company else False,
            "channel": f"{CHANNEL_NAME}_{company.id}" if company else CHANNEL_NAME,
            "last_called": last_called_data,
            "recent_called": recent_called,
            "waiting_tickets": waiting_tickets,
            "waiting_summary": waiting_summary,
            "categories": categories_data,
            "called_caja": called_caja_list,
            "called_ventas": called_ventas_list,
            "waiting_caja": status.get("waiting_caja", 0),
            "waiting_ventas": status.get("waiting_ventas", 0),
            "total_waiting": status.get("total_waiting", 0),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
