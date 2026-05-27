{
    'name': 'Partner Objectives',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Add a table of sales objectives to partner records',
    'description': """
        Allows defining sales objectives per partner with:
        - Date / Period
        - Partner
        - Delivery Address
        - Objective (monetary)

        Objectives are displayed as a tab on the partner form view.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/partner_objective_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
