{
    'name': 'Website Sale B2B Credit Block',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Bloqueo financiero B2B en checkout web por facturas vencidas y límite sobre deuda facturada',
    'description': """
        Módulo Base B2B para EntreDos:
        - Bloqueo automático en checkout por facturas vencidas impagas.
        - Días de gracia configurables por Sitio Web.
        - Control de límite de crédito exclusivamente sobre deuda facturada contable.
        - Mensaje informativo elegante en checkout con cálculo de excedente.
        - Restricción de acceso a tiendas por partner evitando bucles de redirección.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
        'account',
        'sale',
    ],
    'data': [
        'views/website_views.xml',
        'views/res_partner_views.xml',
        'views/cart_templates.xml',
        'views/portal_templates.xml',
        'views/b2b_intranet_alerts.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
