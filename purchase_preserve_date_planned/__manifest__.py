{
    'name': 'Purchase - Preserve Date Planned',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': 'Evita el recalculo automatico de la fecha estimada de llegada al modificar lineas de compra',
    'description': """
        Modulo desarrollado por AlparData.

        Problema que resuelve:
        - En Odoo estandar, cada vez que se modifica una cantidad, unidad de medida
          o proveedor en una orden de compra, el metodo compute recalcula y pisa la
          fecha prevista (date_planned) con la fecha de orden + plazo del proveedor.
        - Esto sobreescribe cualquier fecha estimada fijada manualmente por el usuario
          o definida a nivel de cabecera.

        Solucion:
        - Si la linea ya tiene una fecha prevista (date_planned), se preserva su valor
          durante el recalculo de precios y descripciones.
        - En lineas nuevas sin fecha, se mantiene el calculo automatico inicial del proveedor.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
