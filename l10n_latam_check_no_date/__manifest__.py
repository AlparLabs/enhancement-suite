# l10n_latam_check_no_date/__manifest__.py
{
    'name': 'Cheques Propios sin Fecha Obligatoria',
    'version': '1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Permite emitir cheques propios sin fecha de pago en el cheque.',
    'description': """
        Override del módulo l10n_latam_check para hacer el campo "Fecha del Cheque"
        opcional en cheques propios emitidos (own_checks).
        El pago mantiene su propia fecha contable; el cheque puede quedar sin fecha
        para ser completado después.
    """,
    'author': 'AlparData SAS',
    'depends': [
        'l10n_latam_check',
    ],
    'data': [
        'views/account_payment_register_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OEEL-1',
}
