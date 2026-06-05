{
    'name': 'Project Financial Dashboard',
    'version': '18.0.1.0.0',
    'summary': 'Multi-currency financial indicators on project dashboard',
    'description': """
        Adds a financial summary tab to the project form with invoiced amounts,
        sales and purchase order totals in the project's own currency.
        Critical for Argentina where projects are often priced in USD while
        the company currency is ARS.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'category': 'Project',
    'depends': ['project', 'account', 'analytic', 'sale', 'purchase'],
    'data': [
        'views/project_project_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
