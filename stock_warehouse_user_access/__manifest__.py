{
    'name': 'Acceso por Almacén',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Limita la visibilidad de transferencias y órdenes de compra al almacén asignado a cada usuario.',
    'author': 'AlparData',
    'depends': ['stock', 'purchase_stock'],
    'data': [
        'security/warehouse_access_groups.xml',
        'security/warehouse_access_rules.xml',
        'views/res_users_views.xml',
        'views/stock_picking_views.xml',
        'views/purchase_order_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
