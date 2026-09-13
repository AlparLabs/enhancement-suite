# -*- coding: utf-8 -*-
import base64
from odoo import http, _
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal


class B2BHelpdeskPortal(CustomerPortal):

    @route(['/my/orders/<int:order_id>'], type='http', auth="public", website=True)
    def portal_order_page(self, order_id, **kw):
        response = super().portal_order_page(order_id, **kw)
        if response.status_code == 200 and hasattr(response, 'qcontext') and response.qcontext.get('sale_order'):
            order = response.qcontext['sale_order']
            tickets = request.env['helpdesk.ticket']
            if 'helpdesk.ticket' in request.env:
                Ticket = request.env['helpdesk.ticket'].sudo()
                if 'sale_order_id' in Ticket._fields:
                    tickets = Ticket.search([('sale_order_id', '=', order.id)])
                else:
                    tickets = Ticket.search([
                        ('partner_id.commercial_partner_id', '=', order.partner_id.commercial_partner_id.id),
                        ('name', 'ilike', order.name),
                    ])
            response.qcontext['sale_order_tickets'] = tickets
        return response

    @route(['/my/orders/<int:order_id>/ticket'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_order_ticket(self, order_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env['sale.order'].browse(order_id)

        if not order.exists() or order.partner_id.commercial_partner_id != partner:
            return request.redirect('/my/orders')

        issue_types = [
            ('damaged', _('Mercadería dañada en tránsito (roturas, cajas aplastadas)')),
            ('missing', _('Faltante de mercadería (unidades o bultos no recibidos)')),
            ('quality', _('Desviación de calidad o defecto de empaque')),
            ('other', _('Otro inconveniente con la entrega')),
        ]

        if request.httprequest.method == 'POST':
            issue_type = kw.get('issue_type')
            product_id = int(kw.get('product_id')) if kw.get('product_id') and kw.get('product_id').isdigit() else False
            affected_qty = (kw.get('affected_qty') or '').strip()
            lot_number = (kw.get('lot_number') or '').strip()
            description = (kw.get('description') or '').strip()

            error = None
            if not description:
                error = _("Por favor detalle la descripción del inconveniente observado.")

            if error:
                return request.render('website_sale_b2b_intranet.portal_order_ticket_form', {
                    'order': order,
                    'issue_types': issue_types,
                    'error': error,
                    'submitted_values': kw,
                    'page_name': 'order_ticket',
                })

            issue_label = dict(issue_types).get(issue_type, issue_type or _('Inconveniente con la entrega'))
            product_name = _("Aplica a todo el pedido / Bultos generales")
            if product_id:
                prod = request.env['product.product'].browse(product_id)
                if prod.exists():
                    product_name = prod.display_name

            ticket_description = (
                f"<p><strong>Reporte de Inconveniente de Entrega:</strong></p>"
                f"<ul>"
                f"<li><strong>Pedido de Venta:</strong> {order.name}</li>"
                f"<li><strong>Motivo:</strong> {issue_label}</li>"
                f"<li><strong>Producto afectado:</strong> {product_name}</li>"
                f"<li><strong>Cantidad afectada:</strong> {affected_qty or 'No especificada'}</li>"
                f"<li><strong>N° Lote / Vto:</strong> {lot_number or 'No especificado'}</li>"
                f"</ul>"
                f"<p><strong>Observaciones del cliente:</strong><br/>{description}</p>"
            )

            # Buscar equipo de Helpdesk para Reclamos/Calidad/Logística
            team = False
            if 'helpdesk.team' in request.env:
                team = request.env['helpdesk.team'].sudo().search([
                    '|', '|',
                    ('name', 'ilike', 'reclamo'),
                    ('name', 'ilike', 'calidad'),
                    ('name', 'ilike', 'logistica'),
                ], limit=1)
                if not team:
                    team = request.env['helpdesk.team'].sudo().search([], limit=1)

            ticket_vals = {
                'name': f"Reclamo {order.name} - {issue_label}",
                'partner_id': order.partner_id.id,
                'partner_name': order.partner_id.name,
                'partner_email': order.partner_id.email,
                'partner_phone': order.partner_id.phone,
                'description': ticket_description,
                'team_id': team.id if team else False,
            }
            if 'sale_order_id' in request.env['helpdesk.ticket']._fields:
                ticket_vals['sale_order_id'] = order.id
            if product_id and 'product_id' in request.env['helpdesk.ticket']._fields:
                ticket_vals['product_id'] = product_id

            ticket = request.env['helpdesk.ticket'].sudo().create(ticket_vals)

            # Subir archivos / fotos como evidencia adjunta al ticket
            uploaded_files = request.httprequest.files.getlist('ticket_files')
            single_file = request.httprequest.files.get('ticket_file')
            if single_file and single_file not in uploaded_files:
                uploaded_files.append(single_file)

            for file_storage in uploaded_files:
                if file_storage and file_storage.filename:
                    content = file_storage.read()
                    if content:
                        request.env['ir.attachment'].sudo().create({
                            'name': file_storage.filename,
                            'datas': base64.b64encode(content),
                            'res_model': 'helpdesk.ticket',
                            'res_id': ticket.id,
                            'type': 'binary',
                        })

            # Notificar en el chatter del pedido de venta
            order.message_post(
                body=_(
                    "<strong>Ticket de Helpdesk Creado:</strong> Se registró el ticket %(ticket_name)s "
                    "asociado a este pedido.<br/>"
                    "<strong>Motivo:</strong> %(issue)s<br/>"
                    "<strong>Detalle:</strong> %(desc)s",
                    ticket_name=ticket.name,
                    issue=issue_label,
                    desc=description,
                ),
                subtype_xmlid='mail.mt_note',
            )

            # Redirigir al ticket en el portal nativo de Helpdesk
            return request.redirect(f'/my/ticket/{ticket.id}')

        # Método GET: Renderizar formulario
        return request.render('website_sale_b2b_intranet.portal_order_ticket_form', {
            'order': order,
            'issue_types': issue_types,
            'submitted_values': {},
            'error': None,
            'page_name': 'order_ticket',
        })
