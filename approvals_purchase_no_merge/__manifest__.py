{
    'name': 'Approvals Purchase - No Merge',
    'version': '18.0.1.0.0',
    'summary': 'Prevent RFQ merging across different approval requests',
    'author': 'AlparData',
    'category': 'Purchase',
    'depends': ['approvals_purchase'],
    'data': [
        'views/approval_request_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1',
}
