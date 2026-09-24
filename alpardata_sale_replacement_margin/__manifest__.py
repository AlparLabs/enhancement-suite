{
    'name': 'AlparData - Margen de Reposición en Ventas',
    'version': '19.0.1.0.0',
    'summary': 'Margen de ventas calculado contra el costo de reposición (además del margen contable)',
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Sales/Sales',
    'depends': ['sale_margin', 'alpardata_purchase_replacement_cost'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
