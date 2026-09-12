# -*- coding: utf-8 -*-
import base64
import time
from odoo import fields, http, _
from odoo.exceptions import ValidationError, UserError
from odoo.fields import Command
from odoo.http import request, route
from odoo.addons.account_payment.controllers.portal import PortalAccount


class B2BAccountPaymentPortal(PortalAccount):

    @route(['/my/account/pay'], type='http', auth='user', website=True, sitemap=False)
    def portal_b2b_account_pay(self, amount=None, invoice_ids=None, **kw):
        """
        Renderiza la página de pago online (Mercado Pago / pasarelas) para abonar saldo a cuenta
        o cancelar facturas seleccionadas.
        """
        partner = request.env.user.partner_id.commercial_partner_id
        company = request.website.company_id or request.env.company
        currency = company.currency_id

        # Calcular monto a pagar
        pay_amount = 0.0
        try:
            pay_amount = float(amount or 0.0)
        except (ValueError, TypeError):
            pay_amount = 0.0

        invoices = request.env['account.move']
        selected_inv_ids = []
        if invoice_ids:
            try:
                if isinstance(invoice_ids, str):
                    selected_inv_ids = [int(i) for i in invoice_ids.split(',') if i.strip().isdigit()]
                elif isinstance(invoice_ids, list):
                    selected_inv_ids = [int(i) for i in invoice_ids]
                invoices = request.env['account.move'].search([
                    ('id', 'in', selected_inv_ids),
                    ('partner_id.commercial_partner_id', '=', partner.id),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                ])
            except Exception:
                pass

        if not pay_amount and invoices:
            pay_amount = sum(invoices.mapped('amount_residual'))
        elif not pay_amount:
            # Fallback a la deuda facturada actual si no se especificó monto
            pay_amount = partner.credit if partner.credit > 0 else 0.0

        if pay_amount <= 0:
            return request.redirect('/my/invoices?error=invalid_payment_amount')

        inv_ids_param = ",".join(str(i) for i in invoices.ids)
        reference = f"PAC-{partner.id}-{int(time.time())}"

        invoices_data = {
            'partner': partner,
            'company': company,
            'total_amount': pay_amount,
            'currency': currency,
            'payment_reference': reference,
            'landing_route': '/my/invoices?payment_success=1',
            'transaction_route': f"/my/account/pay/transaction?amount={pay_amount}&reference={reference}&invoice_ids={inv_ids_param}",
        }

        values = {
            'page_name': 'b2b_account_pay',
            'partner': partner,
            'company': company,
            'currency': currency,
            'amount': pay_amount,
            'payment': {
                'amount': pay_amount,
                'reference': reference,
                'currency': currency,
                'date': fields.Date.today(),
            },
            'invoices': invoices,
            'reference': reference,
        }
        common_view_values = self._get_common_page_view_values(invoices_data, **kw)
        values |= common_view_values

        return request.render('website_sale_b2b_account_payment.portal_account_pay_page', values)

    @route('/my/account/pay/transaction', type='jsonrpc', auth='user')
    def portal_b2b_account_pay_transaction(self, amount, reference, invoice_ids='', **kwargs):
        """
        Crea la transacción de pago para el pago a cuenta o de facturas.
        """
        partner = request.env.user.partner_id.commercial_partner_id
        company = request.website.company_id or request.env.company
        currency = company.currency_id

        pay_amount = float(amount or 0.0)
        selected_inv_ids = []
        if invoice_ids:
            try:
                if isinstance(invoice_ids, str):
                    selected_inv_ids = [int(i) for i in invoice_ids.split(',') if i.strip().isdigit()]
                elif isinstance(invoice_ids, list):
                    selected_inv_ids = [int(i) for i in invoice_ids]
            except Exception:
                selected_inv_ids = []

        self._validate_transaction_kwargs(kwargs)
        landing_route = '/my/invoices?payment_success=1'

        tx_sudo = self._create_transaction(
            amount=pay_amount,
            currency_id=currency.id,
            partner_id=partner.id,
            landing_route=landing_route,
            reference_prefix=reference,
            custom_create_values={
                'invoice_ids': [Command.set(selected_inv_ids)] if selected_inv_ids else False,
                'b2b_is_account_payment': True,
            },
            **kwargs
        )
        return tx_sudo._get_processing_values()

    @route(['/my/invoices/upload_receipt'], type='http', auth='user', methods=['GET', 'POST'], website=True, csrf=True)
    def portal_my_invoices_upload_receipt(self, **post):
        """
        Formulario para adjuntar comprobante de transferencia bancaria y crear la rendición con aviso a Tesorería.
        """
        partner = request.env.user.partner_id.commercial_partner_id
        company = request.website.company_id or request.env.company

        if request.httprequest.method == 'POST':
            amount = float(post.get('amount') or 0.0)
            date_str = post.get('date') or fields.Date.today()
            operation_number = post.get('operation_number', '').strip()
            bank_origin = post.get('bank_origin', '').strip()
            notes = post.get('notes', '').strip()
            file = request.httprequest.files.get('receipt_file')

            if amount <= 0:
                return request.redirect('/my/invoices/upload_receipt?error=invalid_amount')
            if not operation_number:
                return request.redirect('/my/invoices/upload_receipt?error=missing_operation')

            # Parsear facturas seleccionadas
            inv_ids = [
                int(k.replace('inv_', ''))
                for k in post.keys()
                if k.startswith('inv_') and post.get(k) == '1'
            ]

            receipt_vals = {
                'partner_id': partner.id,
                'company_id': company.id,
                'amount': amount,
                'date': date_str,
                'operation_number': operation_number,
                'bank_origin': bank_origin,
                'notes': notes,
                'state': 'draft',
            }
            if inv_ids:
                receipt_vals['invoice_ids'] = [Command.set(inv_ids)]

            receipt = request.env['b2b.payment.receipt'].sudo().create(receipt_vals)

            if file and file.filename:
                file_content = file.read()
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': file.filename,
                    'type': 'binary',
                    'datas': base64.b64encode(file_content),
                    'res_model': 'b2b.payment.receipt',
                    'res_id': receipt.id,
                    'mimetype': file.content_type,
                })
                receipt.sudo().write({'attachment_ids': [Command.link(attachment.id)]})

            return request.redirect('/my/invoices?receipt_uploaded=1')

        # GET: Renderizar formulario
        unpaid_invoices = request.env['account.move'].search([
            ('partner_id.commercial_partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ], order='invoice_date_due asc')

        values = {
            'page_name': 'upload_receipt',
            'partner': partner,
            'company': company,
            'unpaid_invoices': unpaid_invoices,
            'today': fields.Date.today(),
            'financial_status': partner._get_b2b_financial_status(request.website),
        }
        return request.render('website_sale_b2b_account_payment.upload_receipt_page', values)
