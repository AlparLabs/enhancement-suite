# __manifest__.py
{
    'name': 'Convertir Factura a Recibo Interno',
    'version': '18.0.2.0.0',
    'category': 'Accounting',
    'summary': 'Transforma borradores de facturas en recibos contables internos',
    'author': 'AlparData SAS / Gemini',
    'depends': ['account'],
    'data': [
        'views/res_config_settings_view.xml',
        'views/account_move_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}