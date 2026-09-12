# -*- coding: utf-8 -*-
{
    'name': 'Website B2B Intranet: Marketing Materials & Order Claims',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Intranet B2B para franquicias y distribuidores: Repositorio de materiales POP/marketing y gestión de reclamos de entrega',
    'author': 'AlparLabs',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'website',
        'sale',
        'mail',
        'website_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/b2b_intranet_security.xml',
        'data/ir_sequence_data.xml',
        'views/b2b_marketing_material_views.xml',
        'views/b2b_order_claim_views.xml',
        'views/portal_templates.xml',
        'views/materials_templates.xml',
        'views/claim_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
