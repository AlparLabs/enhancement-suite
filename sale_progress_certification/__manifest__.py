{
    'name': 'Sale Progress Certification',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Añade opción de facturar por % de Avance (Certificación) en Ventas',
    'description': """
        Este módulo extiende el wizard de creación de facturas en Ventas.
        Agrega la opción 'Certificación por % de avance'.
        
        Funcionalidad:
        - Crea una línea de anticipo (Down Payment) usando un producto de servicio específico.
        - Permite facturar hitos parciales que se descontarán de la factura final.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'sale_management',
        'account',
    ],
    'data': [
        'data/product_data.xml',
        'views/sale_advance_payment_inv_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}