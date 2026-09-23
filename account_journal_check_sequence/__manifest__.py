# account_journal_check_sequence/__manifest__.py
{
    'name': 'Secuencia de Cheques Propios en Diarios de Banco',
    'version': '19.0.1.3.0',
    'category': 'Accounting/Localizations',
    'summary': 'Chequeras de cheques propios compartibles entre diarios de banco y compañías.',
    'description': """
        Chequeras de Cheques Propios (Odoo 19 / ADHOC)
        ==============================================
        * Numeración secuencial ("tipo chequera") en un modelo propio, account.checkbook.
        * Varios diarios de banco, incluso de distintas compañías, pueden compartir la misma chequera y siguen un único correlativo.
        * Sugiere automáticamente el próximo número de cheque al registrar pagos (compatible con Órdenes de Pago de ADHOC y pagos estándar).
        * Permite al usuario editar libremente el número de cheque si necesita saltear números.
        * Actualiza automáticamente el contador al confirmar/publicar el pago, sin permitir que retroceda.
        * Bloquea números de cheque ya emitidos en la misma chequera, sin importar el diario o la compañía.
        * Asistente para unificar las chequeras de diarios que emiten de la misma chequera física.
        * Alcance: método de pago "Cheque Propio" (own_checks) de l10n_latam_check.
        * Serializa los pagos publicados en paralelo sobre la misma chequera.
    """,
    'author': 'AlparData SAS',
    'website': 'https://alpardata.com',
    'license': 'OEEL-1',
    'depends': [
        'account',
        'l10n_latam_check',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/account_checkbook_security.xml',
        'views/account_checkbook_views.xml',
        'views/account_journal_views.xml',
        'views/account_payment_views.xml',
        'wizards/account_checkbook_merge_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
