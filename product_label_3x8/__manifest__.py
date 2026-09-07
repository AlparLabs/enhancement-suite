{
    'name': 'Product Label 3x8 (65x35mm)',
    'version': '19.0.1.0.0',
    'category': 'Product',
    'summary': 'Etiquetas de productos 3x8 en hoja A4 (65x35mm) para portaprecios',
    'description': """
        Agrega el formato de impresión 3x8 (24 etiquetas por hoja A4)
        con dimensiones de 65x35mm aprox., optimizado para portaprecios de 130x35mm.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': [
        'product',
    ],
    'data': [
        'report/product_label_actions.xml',
        'report/product_label_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
