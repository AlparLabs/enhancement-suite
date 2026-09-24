{
    'name': 'AlparData - Margen de Reposición en POS',
    'version': '19.0.1.0.0',
    'summary': 'Margen del punto de venta calculado contra el costo de reposición',
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Sales/Point of Sale',
    'depends': ['point_of_sale', 'alpardata_purchase_replacement_cost'],
    'data': [],  # la tarea 6 agrega las vistas
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
