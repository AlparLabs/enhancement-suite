# -*- coding: utf-8 -*-
{
    'name': 'Website B2B Account Payments & Transfer Receipts',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Pago a cuenta online (Mercado Pago / pasarelas) y rendición digital de comprobantes de transferencia bancaria B2B',
    'author': 'AlparLabs',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'account_payment',
        'payment',
        'portal',
        'website',
        'website_sale_b2b_credit_block',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/b2b_payment_receipt_views.xml',
        'views/portal_templates.xml',
        'views/receipt_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
