{
    'name': 'Sale Credit Limit Approval',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Bloquea la confirmación de ventas si el cliente supera su límite de crédito',
    'description': """
        Este módulo extiende el flujo de confirmación de órdenes de venta.
        Si el cliente supera su límite de crédito, la orden queda en estado
        'Esperando Aprobación' y debe ser autorizada por el supervisor asignado
        o por un administrador del sistema.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'sale_management',
        'account',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_credit_approval_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'security/security.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
