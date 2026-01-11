{
    'name': 'Split Venta 50/50 (Factura/Recibo)',
    'version': '18.0.1.0.1',
    'category': 'Sales',
    'summary': 'Factura 50% Oficial y 50% Recibo Interno',
    'author': 'AlparData',
    'depends': ['sale_management', 'account_invoice_to_receipt'],
    'data': [
        'views/sale_advance_payment_inv_views.xml',
    ],
    'installable': True,
    'license': 'AGPL-3',
}