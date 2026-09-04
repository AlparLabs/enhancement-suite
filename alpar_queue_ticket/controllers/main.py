# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class QueueDisplayController(http.Controller):

    @http.route("/turnos/pantalla", type="http", auth="public", website=False, sitemap=False)
    def queue_display_page(self, **kwargs):
        """Página pública para proyectar en Smart TV o monitores de sala de espera."""
        company = request.env.company
        data = request.env["queue.ticket"].sudo().with_company(company).get_display_data()
        values = {
            "initial_data_json": json.dumps(data),
            "company_name": company.name,
            "channel_name": data.get("channel", "alpar_queue_channel"),
        }
        return request.render("alpar_queue_ticket.queue_display_page", values)

    @http.route("/turnos/api/display_data", type="json", auth="public", methods=["POST", "GET"])
    def queue_display_data_api(self, **kwargs):
        """Endpoint JSON-RPC para polling o refresco de datos de la pantalla."""
        company = request.env.company
        return request.env["queue.ticket"].sudo().with_company(company).get_display_data()

    @http.route(["/turnos/api/queue_types", "/turnos/api/categories"], type="json", auth="public", methods=["POST"])
    def queue_types_json(self, **kwargs):
        """Endpoint JSON-RPC para obtener las categorías de turnos activas."""
        company = request.env.company
        return self._get_queue_types_data(company)

    @http.route(["/turnos/api/queue_types", "/turnos/api/categories"], type="http", auth="public", methods=["GET"], csrf=False)
    def queue_types_http(self, **kwargs):
        """Endpoint REST GET directo para terminales Android / Kiosco."""
        company = request.env.company
        data = self._get_queue_types_data(company)
        return request.make_json_response(data)

    def _get_queue_types_data(self, company):
        types = request.env["queue.ticket.type"].sudo().search([
            ("active", "=", True),
            "|", ("company_id", "=", False), ("company_id", "=", company.id),
        ], order="sequence, id")
        return [
            {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "prefix": t.prefix,
                "sequence": t.sequence,
                "icon": t.icon or "fa-ticket",
                "color": t.color or "#3498db",
                "description": t.description or "",
            }
            for t in types
        ]

    @http.route("/turnos/api/kiosk_ticket", type="json", auth="public", methods=["POST"])
    def create_kiosk_ticket_api(self, **kwargs):
        """Endpoint JSON-RPC para sacar turnos desde terminales Kiosco Android."""
        company = request.env.company
        data = kwargs.get("params", kwargs)
        return request.env["queue.ticket"].sudo().with_company(company).create_from_kiosk(data)

    @http.route("/turnos/api/kiosk_ticket/rest", type="http", auth="public", methods=["POST"], csrf=False)
    def create_kiosk_ticket_rest(self, **kwargs):
        """Endpoint REST POST directo para terminales Kiosco Android."""
        company = request.env.company
        try:
            body = json.loads(request.httprequest.data.decode("utf-8")) if request.httprequest.data else kwargs
        except Exception:
            body = kwargs
        ticket_data = request.env["queue.ticket"].sudo().with_company(company).create_from_kiosk(body)
        return request.make_json_response(ticket_data)
