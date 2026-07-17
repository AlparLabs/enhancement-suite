{
    'name': 'Sale Stock Lot Selection',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Let the salesperson pick the lots to deliver from the sale order line',
    'description': """
        On a lot-tracked sale order line, the salesperson can open a popup
        listing the available lots of the order's warehouse and choose which
        lot(s) — and how much of each — to deliver. On order confirmation
        those lots are reserved immediately on the delivery. Anything not
        covered by the selection (or no longer available) falls back to
        Odoo's native automatic reservation strategy.
        A visual badge on the line shows whether a lot-tracked product still
        has no lot selected.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'stock_forecasted_lots'],
    'data': [
        'security/ir.model.access.csv',
        'views/lot_selection_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
