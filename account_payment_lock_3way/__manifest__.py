# account_payment_lock_3way/__manifest__.py
{
    'name': 'Bloqueo de Pagos por 3-Way Match',
    'version': '18.0.1.1.0',
    'category': 'Accounting',
    'summary': 'Bloquea pagos si hay discrepancias de precio/cantidad hasta recibir NC o aprobación.',
    'author': 'AlparData SAS / Gemini',
    'depends': [
        'base',
        'account', 
        'purchase', 
        'account_3way_match'  # CRÍTICO: Necesario para detectar las excepciones
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OEEL-1',
}