{
    'name': 'Separador decimal configurable en TXT de liquidación',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Permite exportar los TXT de liquidación con punto o coma decimal',
    'description': """
        Módulo desarrollado por AlparData.

        Problema que resuelve:
        - El aplicativo SIAp - SI.CO.RE. permite configurar con qué separador
          decimal lee los archivos de importación de retenciones/percepciones
          (Importar/Exportar Retenciones/Percepciones -> Configuración de
          Importación de Retenciones -> Separador de decimales).
        - Hasta el Release 22 el default era coma; desde el Release 23 es punto.
          Muchos estudios contables lo tienen fijado en coma a mano, o lo
          arrastran de una instalación anterior.
        - El TXT que genera l10n_ar_account_tax_settlement usa punto. Si el
          SICORE del receptor está configurado en coma, rechaza el archivo con
          "el campo X debería ser Numérico Positivo" en los cuatro campos que
          llevan decimales (importe del comprobante, base de cálculo, importe
          de la retención y porcentaje de exclusión).

        Solución:
        - Un campo en el diario que permite elegir el separador decimal del TXT,
          aplicado sobre el resultado del dispatch que ya existe en el módulo
          base (get_tax_settlement_files_values).
        - El default es punto, así que instalar el módulo no altera la salida de
          ninguna instancia existente.

        Aclaración importante: el archivo que genera Odoo es correcto. La
        solución correcta para el usuario final sigue siendo configurar el
        SICORE en "punto". Este módulo es la vía de escape para los casos en que
        el receptor del archivo no modifica su configuración.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'license': 'OEEL-1',
    'depends': [
        'l10n_ar_account_tax_settlement',
    ],
    'data': [
        'views/account_journal_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
