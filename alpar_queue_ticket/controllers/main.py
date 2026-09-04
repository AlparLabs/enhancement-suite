# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class QueueDisplayController(http.Controller):

    @http.route("/turnos/pantalla", type="http", auth="public", website=False, sitemap=False)
    def queue_display_page(self, **kwargs):
        """P?gina p?blica para proyectar en Smart TV o monitores de sala de espera."""
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
        """Endpoint JSON para polling o refresco de datos de la pantalla."""
        company = request.env.company
        return request.env["queue.ticket"].sudo().with_company(company).get_display_data()

    @http.route("/turnos/api/kiosk_ticket", type="json", auth="public", methods=["POST"])
    def create_kiosk_ticket_api(self, **kwargs):
        """Endpoint directo para sacar turnos desde terminales Kiosco Android."""
        company = request.env.company
        data = kwargs.get("params", kwargs)
        return request.env["queue.ticket"].sudo().with_company(company).create_from_kiosk(data)
