{
    'name': 'Partner Channel',
    'version': '19.0.1.0.0',
    'summary': 'Channel and Channel Detail for contacts, propagated to Sale Orders',
    'description': """
        Adds a Channel (Many2one) and Channel Details (Many2many) to contacts.
        Each Channel Detail belongs to a Channel, so the available details are
        filtered by the selected Channel.
        These fields are propagated to Sale Orders (auto-filled from the customer,
        but editable on the order).
    """,
    'category': 'Sales',
    'author': 'AlparData',
    'depends': ['sale', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_channel_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
