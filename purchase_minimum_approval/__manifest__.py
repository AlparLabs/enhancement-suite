{
    'name': 'Purchase Minimum Approval',
    'version': '19.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Bloquea la confirmación de compras por debajo del mínimo del proveedor',
    'description': """
        Este módulo extiende el flujo de confirmación de órdenes de compra.
        Si el subtotal de la orden no alcanza el mínimo de compra configurado
        en el proveedor, la orden queda en estado 'Esperando Aprobación' y debe
        ser autorizada por un miembro del grupo aprobador de compras.

        Análogo al límite de crédito de ventas, pero para compras.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'purchase',
    ],
    'data': [
        'security/security.xml',
        'views/purchase_order_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
