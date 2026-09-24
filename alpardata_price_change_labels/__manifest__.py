{
    'name': 'AlparData - Margen Erosionado y Etiquetas Pendientes',
    'version': '19.0.1.0.0',
    'summary': 'Alerta de recargo bajo objetivo sobre costo de reposición y cola de etiquetas de góndola a reimprimir',
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Inventory/Purchase',
    'depends': ['alpardata_purchase_replacement_cost', 'product_label_3x8'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
