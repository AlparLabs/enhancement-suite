# account_journal_check_sequence/__manifest__.py
{
    'name': 'Secuencia de Cheques Propios en Diarios de Banco',
    'version': '19.0.2.4.0',
    'category': 'Accounting/Localizations',
    'summary': 'Gestión de chequeras y numeración secuencial de cheques propios por diario de banco.',
    'description': """
        Secuencia de Cheques Propios por Diario de Banco (Odoo 19 / ADHOC)
        ===================================================================
        * Añade numeración secuencial ("tipo chequera") a nivel de cada diario de banco.
        * Aplica a los métodos "Cheques propios" (own_checks, de l10n_latam_check) y
          "Cheques" (check_printing). Para check_printing, Odoo ya trae numeración
          nativa (check_manual_sequencing / check_next_number): una constraint impide
          activar las dos sobre el mismo diario.
        * Sugiere automáticamente el próximo número de cheque al registrar pagos (compatible con Órdenes de Pago de ADHOC y pagos estándar).
        * Permite al usuario editar libremente el número de cheque si necesita saltear números.
        * Actualiza automáticamente el contador del diario al confirmar/publicar el pago.
        * Permite modificar el próximo número directamente desde la configuración del diario.
    """,
    'author': 'AlparData SAS',
    'website': 'https://alpardata.com',
    'license': 'OEEL-1',
    'depends': [
        'account',
        'l10n_latam_check',
    ],
    'data': [
        'views/account_journal_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
