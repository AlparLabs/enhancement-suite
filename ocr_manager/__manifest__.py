# -*- coding: utf-8 -*-
{
    'name': "OCR Manager - IA Generativa",
    'summary': "Gestor avanzado de digitalización con Gemini/OpenAI",
    'version': '19.0.1.0.1',
    'category': 'Accounting/Accounting',
    'author': "AlparData & Gemini",
    'website': "www.alpardata.com.ar",
    'license': 'OPL-1',
    'depends': ['base', 'account', 'iap_extract', 'account_invoice_extract'],
    'data': [
        'security/ir.model.access.csv',
        'data/ocr_prompt_data.xml',
        'views/res_company_views.xml',
        'views/ocr_prompt_views.xml',
        'wizard/ocr_bulk_digitize_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
}