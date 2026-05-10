{
    'name': 'Partner Group Ledger',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Adds Partner Group and groups Partner Ledger by it',
    'description': """
        Adds a new Partner Group concept.
        Groups the standard Partner Ledger report by this new Partner Group.
    """,
    'author': 'AlparData SAS / Gemini',
    'depends': ['account', 'account_reports'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_group_views.xml',
        'views/res_partner_views.xml',
        'data/account_report_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
