# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class QueueDisplayController(http.Controller):

    @http.route("/turnos/pantalla", type="http", auth="public", website=False, sitemap=False)
    def queue_display_page(self, **kwargs):
        """Página pública para proyectar en Smart TV o monitores de sala de espera."""
        company = self._resolve_company(**kwargs)
        data = request.env["queue.ticket"].sudo().with_company(company).get_display_data(company_id=company.id)
        values = {
            "initial_data_json": json.dumps(data),
            "company_name": company.name,
            "company_id": company.id,
            "last_called": data.get("last_called"),
            "recent_called": data.get("recent_called", []),
            "waiting_tickets": data.get("waiting_tickets", []),
            "waiting_summary": data.get("waiting_summary", []),
            "total_waiting": data.get("total_waiting", 0),
            "categories": data.get("categories", []),
            "channel_name": data.get("channel", "alpar_queue_channel"),
        }
        return request.render("alpar_queue_ticket.queue_display_page", values)

    @http.route("/turnos/api/display_data", type="json", auth="public", methods=["POST", "GET"])
    def queue_display_data_api(self, **kwargs):
        """Endpoint JSON para polling o refresco de datos de la pantalla."""
        data_params = kwargs.get("params", kwargs)
        company = self._resolve_company(**data_params)
        return request.env["queue.ticket"].sudo().with_company(company).get_display_data(company_id=company.id)

    def _resolve_company(self, **kwargs):
        company_id = kwargs.get("company_id")
        if company_id:
            try:
                comp = request.env["res.company"].sudo().browse(int(company_id)).exists()
                if comp:
                    return comp
            except Exception:
                pass
        if not request.env.user._is_public() and request.env.user.company_id:
            return request.env.user.company_id
        return request.env.company

    @http.route(["/turnos/api/queue_types", "/turnos/api/categories"], type="json", auth="public", methods=["POST"])
    def queue_types_json(self, **kwargs):
        """Endpoint JSON-RPC para obtener las categorias de turnos activas."""
        company = self._resolve_company(**kwargs)
        allow_fallback = not bool(kwargs.get("company_id"))
        return self._get_queue_types_data(company, allow_fallback=allow_fallback)

    @http.route(["/turnos/api/queue_types", "/turnos/api/categories"], type="http", auth="public", methods=["GET"], csrf=False)
    def queue_types_http(self, **kwargs):
        """Endpoint REST GET directo para terminales Android / Kiosco."""
        company = self._resolve_company(**kwargs)
        allow_fallback = not bool(kwargs.get("company_id"))
        data = self._get_queue_types_data(company, allow_fallback=allow_fallback)
        return request.make_json_response(data)

    def _get_queue_types_data(self, company, allow_fallback=True):
        types = request.env["queue.ticket.type"].sudo().search([
            ("active", "=", True),
            "|", ("company_id", "=", False), ("company_id", "=", company.id),
        ], order="sequence, id")

        # Fallback multi-compañía: Si no hay tipos suficientes para la compañía por defecto de la sesión
        # y existen más tipos activos en el sistema, traerlos todos
        if len(types) <= 2 and allow_fallback:
            all_types = request.env["queue.ticket.type"].sudo().search([
                ("active", "=", True),
            ], order="sequence, id")
            if len(all_types) > len(types):
                types = all_types

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
        data = kwargs.get("params", kwargs)
        company = self._resolve_company(**data)
        return request.env["queue.ticket"].sudo().with_company(company).create_from_kiosk(data)

    @http.route("/turnos/api/kiosk_ticket/rest", type="http", auth="public", methods=["POST"], csrf=False)
    def create_kiosk_ticket_rest(self, **kwargs):
        """Endpoint REST POST directo para terminales Kiosco Android."""
        try:
            body = json.loads(request.httprequest.data.decode("utf-8")) if request.httprequest.data else kwargs
        except Exception:
            body = kwargs
        company = self._resolve_company(**body)
        ticket_data = request.env["queue.ticket"].sudo().with_company(company).create_from_kiosk(body)
        return request.make_json_response(ticket_data)
