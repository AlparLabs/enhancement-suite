{
    'name': 'Restricción de Entrega sin Factura',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Impide validar entregas si la venta no está facturada, con excepción para gerentes.',
    'author': 'AlparData',
    'depends': ['base', 'stock', 'sale'],
    'data': [
        'security/security.xml',
        'views/stock_picking_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}