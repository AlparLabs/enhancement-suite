{
    'name': 'Vendor Cash Closure Report',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Daily sales/invoices closure report grouped by salesperson, for retail cash control',
    'description': """
        Replicates a legacy "Cierre de Caja" report: for a given date, lists
        every posted customer invoice/credit note and customer payment,
        grouped by salesperson, split into Contado / Cuenta Corriente / NC /
        MiPyme (FCE) columns, with per-vendor and grand-total subtotals.
        Downloadable as PDF (landscape) and XLSX from a date wizard.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': ['account', 'sale', 'point_of_sale', 'l10n_latam_invoice_document'],
    'data': [
        'security/ir.model.access.csv',
        'report/report_cash_closure_vendor.xml',
        'views/report_cash_closure_vendor_template.xml',
        'wizard/cash_closure_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
