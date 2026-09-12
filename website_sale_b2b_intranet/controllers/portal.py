# -*- coding: utf-8 -*-
import base64
from odoo import http, _
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal


class B2BIntranetPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id.commercial_partner_id
        website = request.website

        if 'material_count' in counters:
            domain = [
                ('active', '=', True),
                '|', ('website_ids', '=', False), ('website_ids', 'in', [website.id]),
            ]
            values['material_count'] = request.env['b2b.marketing.material'].search_count(domain)

        if 'claim_count' in counters:
            domain = [
                ('commercial_partner_id', '=', partner.id),
            ]
            values['claim_count'] = request.env['b2b.order.claim'].search_count(domain)

        return values

    # -------------------------------------------------------------------------
    # Repositorio de Materiales POP & Marketing B2B
    # -------------------------------------------------------------------------

    @route(['/my/materials'], type='http', auth='user', website=True)
    def portal_my_materials(self, category=None, search=None, **kw):
        website = request.website
        domain = [
            ('active', '=', True),
            '|', ('website_ids', '=', False), ('website_ids', 'in', [website.id]),
        ]

        valid_categories = dict(request.env['b2b.marketing.material']._fields['category'].selection)
        if category and category in valid_categories:
            domain.append(('category', '=', category))

        if search:
            domain.append(('name', 'ilike', search.strip()))

        materials = request.env['b2b.marketing.material'].search(domain)

        # Contadores por categoría para insignias en pestañas
        base_domain = [
            ('active', '=', True),
            '|', ('website_ids', '=', False), ('website_ids', 'in', [website.id]),
        ]
        category_counts = {}
        for cat_key in valid_categories.keys():
            category_counts[cat_key] = request.env['b2b.marketing.material'].search_count(
                base_domain + [('category', '=', cat_key)]
            )
        total_materials = request.env['b2b.marketing.material'].search_count(base_domain)

        values = {
            'materials': materials,
            'selected_category': category,
            'categories': valid_categories,
            'category_counts': category_counts,
            'total_materials': total_materials,
            'search_term': search or '',
            'page_name': 'materials',
        }
        return request.render('website_sale_b2b_intranet.portal_my_materials', values)

    @route(['/my/materials/<int:material_id>/download'], type='http', auth='user', website=True)
    def portal_my_material_download(self, material_id, **kw):
        website = request.website
        material = request.env['b2b.marketing.material'].browse(material_id)

        if not material.exists() or not material.active:
            return request.redirect('/my/materials')

        # Verificar restricción de canal web
        if material.website_ids and website.id not in material.website_ids.ids:
            return request.redirect('/my/materials')

        if not material.file:
            return request.redirect('/my/materials')

        # Registrar contador de descargas
        material.action_register_download()

        file_content = base64.b64decode(material.file)
        filename = material.file_name or f"{material.name}.dat"
        headers = [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Disposition', http.content_disposition(filename)),
            ('Content-Length', len(file_content)),
        ]
        return request.make_response(file_content, headers=headers)

    # -------------------------------------------------------------------------
    # Gestión de Reclamos y Calidad de Envíos
    # -------------------------------------------------------------------------

    @route(['/my/orders/<int:order_id>/claim'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_order_claim(self, order_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env['sale.order'].browse(order_id)

        if not order.exists() or order.partner_id.commercial_partner_id != partner:
            return request.redirect('/my/orders')

        claim_types = request.env['b2b.order.claim']._fields['claim_type'].selection

        if request.httprequest.method == 'POST':
            claim_type = kw.get('claim_type')
            product_id = int(kw.get('product_id')) if kw.get('product_id') and kw.get('product_id').isdigit() else False
            affected_qty = 0.0
            try:
                affected_qty = float(kw.get('affected_qty') or 0.0)
            except (ValueError, TypeError):
                affected_qty = 0.0

            lot_number = (kw.get('lot_number') or '').strip()
            description = (kw.get('description') or '').strip()

            error = None
            if not description:
                error = _("Por favor detalle la descripción del inconveniente observado.")
            elif not claim_type or claim_type not in dict(claim_types):
                error = _("Por favor seleccione un motivo válido para el reclamo.")

            if error:
                return request.render('website_sale_b2b_intranet.portal_order_claim_form', {
                    'order': order,
                    'claim_types': claim_types,
                    'error': error,
                    'submitted_values': kw,
                    'page_name': 'order_claim',
                })

            # Subida de evidencia fotográfica (remito, bulto, producto)
            uploaded_files = request.httprequest.files.getlist('claim_files')
            single_file = request.httprequest.files.get('claim_file')
            if single_file and single_file not in uploaded_files:
                uploaded_files.append(single_file)

            attachment_ids = []
            for file_storage in uploaded_files:
                if file_storage and file_storage.filename:
                    content = file_storage.read()
                    if content:
                        attachment = request.env['ir.attachment'].sudo().create({
                            'name': file_storage.filename,
                            'datas': base64.b64encode(content),
                            'res_model': 'b2b.order.claim',
                            'res_id': 0,
                            'type': 'binary',
                        })
                        attachment_ids.append(attachment.id)

            # Creación del reclamo
            claim = request.env['b2b.order.claim'].sudo().create({
                'order_id': order.id,
                'claim_type': claim_type,
                'product_id': product_id,
                'affected_qty': affected_qty,
                'lot_number': lot_number,
                'description': description,
                'attachment_ids': [(6, 0, attachment_ids)],
            })

            # Vincular los adjuntos creados al ID final del reclamo
            if attachment_ids:
                request.env['ir.attachment'].sudo().browse(attachment_ids).write({'res_id': claim.id})

            return request.redirect(f'/my/claims?claim_created={claim.name}')

        # Método GET: Renderizar formulario
        return request.render('website_sale_b2b_intranet.portal_order_claim_form', {
            'order': order,
            'claim_types': claim_types,
            'submitted_values': {},
            'error': None,
            'page_name': 'order_claim',
        })

    @route(['/my/claims'], type='http', auth='user', website=True)
    def portal_my_claims(self, state=None, search=None, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        domain = [('commercial_partner_id', '=', partner.id)]

        states_dict = dict(request.env['b2b.order.claim']._fields['state'].selection)
        if state and state in states_dict:
            domain.append(('state', '=', state))

        if search:
            domain.append('|', ('name', 'ilike', search.strip()), ('order_id.name', 'ilike', search.strip()))

        claims = request.env['b2b.order.claim'].search(domain, order='date desc, id desc')

        # Contadores de estado para filtros rápidos
        base_domain = [('commercial_partner_id', '=', partner.id)]
        state_counts = {}
        for st_key in states_dict.keys():
            state_counts[st_key] = request.env['b2b.order.claim'].search_count(
                base_domain + [('state', '=', st_key)]
            )
        total_claims = request.env['b2b.order.claim'].search_count(base_domain)

        values = {
            'claims': claims,
            'selected_state': state,
            'states': states_dict,
            'state_counts': state_counts,
            'total_claims': total_claims,
            'search_term': search or '',
            'claim_created': kw.get('claim_created'),
            'page_name': 'claims',
        }
        return request.render('website_sale_b2b_intranet.portal_my_claims', values)
