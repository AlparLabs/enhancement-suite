{
    'name': 'Partner Sales Team Sync',
    'version': '19.0.1.0.0',
    'summary': 'Sync Sales Team from Partner to Sale Order',
    'description': """
        Extends res.partner to include a preferred Sales Team.
        Automatically assigns the Sales Team on Sale Orders based on the selected customer.
    """,
    'category': 'Sales',
    'author': 'AlparData',
    'depends': ['sale', 'sales_team'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
