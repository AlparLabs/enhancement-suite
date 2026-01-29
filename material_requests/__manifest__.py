{
    'name': 'Material Requests (PIM/SIM)',
    'version': '18.0.1.0.1',
    'summary': 'Manage PIM (Internal Material Requests) and SIM (Purchase Requests)',
    'author': 'AlparData',
    'category': 'Construction/Inventory',
    'depends': ['project', 'stock', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/pim_views.xml',
        'views/sim_views.xml',
        'views/purchase_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}