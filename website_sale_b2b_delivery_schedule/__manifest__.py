# -*- coding: utf-8 -*-
{
    'name': 'Website Sale B2B Delivery Schedule & Shifts',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Programación de fecha de entrega y turnos (Mañana/Tarde) en checkout B2B sincronizado con almacén',
    'author': 'AlparLabs',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
        'sale',
    ],
    'data': [
        'views/website_views.xml',
        'views/sale_order_views.xml',
        'views/checkout_templates.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
