{
    'name': 'Paid Invoice Export',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Export paid/partial customer invoices to Excel, one row per applied payment',
    'description': """
        Wizard to export customer invoices in payment_state paid / partial /
        in_payment, expanded one row per applied payment (with the amount
        applied in company currency, payment reference, date, and a credit-note
        flag). Replaces the external JSON-RPC extraction script.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/paid_invoice_export_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
