{
    'name': 'Partner Objectives',
    'version': '19.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Add a table of sales objectives to partner records',
    'description': """
        Allows defining sales objectives per partner with:
        - Start Date / End Date (objective period)
        - Partner
        - Delivery Address
        - Objective (monetary and quantity)
        - Dozens sold in the period, computed from confirmed sale orders

        Products carry a 'Counts for Objectives' flag and a 'Dozens per Unit'
        value used to compute how many dozens were sold to a partner.

        Objectives are displayed as a tab on the partner form view.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/partner_objective_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
