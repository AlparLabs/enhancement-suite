# -*- coding: utf-8 -*-
{
    'name': 'Website B2B Order Helpdesk Bridge',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Reportar inconvenientes de entrega directamente desde el pedido hacia Helpdesk nativo de Odoo',
    'author': 'AlparLabs',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'website',
        'sale',
        'helpdesk',
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
