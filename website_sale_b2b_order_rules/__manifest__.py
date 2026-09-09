# -*- coding: utf-8 -*-
{
    'name': 'Website Sale B2B Order Rules & Quotas',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Regulación de compras B2B: máximos por producto y canal, y ventanas semanales de pedido',
    'author': 'AlparLabs',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
        'sale',
        'website_sale_b2b_credit_block',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/website_views.xml',
        'views/product_template_views.xml',
        'views/shop_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
