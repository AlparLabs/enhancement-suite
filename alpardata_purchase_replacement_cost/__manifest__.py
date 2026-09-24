{
    'name': 'AlparData - Costo de Reposición',
    'version': '19.0.1.0.0',
    'summary': 'Costo de reposición: lista con bonificaciones en cascada, pronto pago, flete, percepciones e impuestos internos',
    'description': """
        Extiende el Costo de Referencia con un Costo de Reposición desglosado:

            neto       = lista × (1 − b1) × (1 − b2) × …
            reposición = neto × (1 − pronto pago + flete + percepción + internos)

        - Condiciones comerciales por proveedor (por empresa), con excepción por
          ficha de proveedor del producto.
        - Impuestos internos por categoría y producto.
        - Base "Costo de Reposición" en listas de precios.
        - Bonificaciones en cascada como descuento en órdenes de compra.
        - Semáforo de divergencia contra el neto bonificado.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Inventory/Purchase',
    'depends': ['alpardata_purchase_reference_cost'],
    'data': [
        'views/res_partner_views.xml',
        'views/product_category_views.xml',
        'views/product_supplierinfo_views.xml',
        'views/product_template_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
