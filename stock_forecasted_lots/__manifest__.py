{
    'name': 'Stock Forecasted Lots',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Show available lots (e.g. cable coils) in the stock forecasted report',
    'description': """
        Adds an "Available lots" section to the stock Forecasted Report
        (the one opened from a sale order line's availability icon or a
        product's Forecast button). Lists, for the warehouse selected in
        the report, each lot's on-hand, reserved, and available quantity —
        so a salesperson can see how much stock remains on a given lot
        (e.g. meters left on a cable coil) and offer the customer the
        remaining quantity to close out the lot.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': ['sale_stock'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'stock_forecasted_lots/static/src/stock_forecasted/forecasted_details.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
