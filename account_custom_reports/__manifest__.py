{
    'name': 'Account Custom Reports',
    'version': '18.0.0.0.1',
    'category': 'Accounting/Accounting',
    'summary': 'Customizations for Accounting Reports',
    'description': """
        This module contains custom modifications for accounting reports.
        - Hides Initial Balance in Partner Ledger.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'depends': ['account_reports'],
    'data': [
        'data/account_report_data.xml',
        'views/account_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_custom_reports/static/src/xml/custom_filters.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}