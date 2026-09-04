# -*- coding: utf-8 -*-
{
    'name': 'AlparLabs Queue Ticket - Turnera Inteligente POS & Ventas',
    'version': '19.0.1.0.1',
    'category': 'Point of Sale',
    'summary': 'Sistema de gestión de turnos y filas integrado con Kiosco Android, Odoo POS, Ventas y Pantalla TV',
    'author': 'AlparLabs',
    'website': 'https://alparlabs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'bus',
        'sale_management',
        'point_of_sale',
    ],
    'data': [
        'security/queue_security.xml',
        'security/ir.model.access.csv',
        'data/queue_ticket_type_data.xml',
        'views/queue_ticket_type_views.xml',
        'views/queue_ticket_views.xml',
        'views/pos_config_views.xml',
        'views/queue_ticket_menus.xml',
        'views/queue_display_templates.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'alpar_queue_ticket/static/src/app/navbar/navbar_patch.js',
            'alpar_queue_ticket/static/src/app/navbar/navbar_patch.xml',
            'alpar_queue_ticket/static/src/app/navbar/navbar_patch.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
