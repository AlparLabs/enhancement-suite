{
    'name': 'Material Requests (PIM/SIM)',
    'version': '18.0.1.0.0',
    'summary': 'Manage PIM (Internal Material Requests) and SIM (Purchase Requests)',
    'author': 'AlparData',
    'category': 'Construction/Inventory',
    'depends': ['base', 'project', 'stock', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/pim_view.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}