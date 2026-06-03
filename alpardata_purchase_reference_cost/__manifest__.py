{
    'name': 'AlparData - Costo de Referencia Comercial',
    'version': '19.0.2.0.0',
    'summary': 'Costo de referencia por proveedor con historial de listas de precios',
    'description': """
        Módulo desarrollado por AlparData para Grupo Broda.

        Problema que resuelve:
        - En Odoo con AVCO, cada recepción de mercadería mueve el standard_price
          automáticamente via stock.valuation.layer.
        - Esto hace que el margen calculado en listas de precios fluctúe
          con cada compra, lo cual es inaceptable para Retail.
        - La solución: separar el costo contable (AVCO real) del costo comercial
          (reference_cost) que se usa para margen y precio de venta.

        Funcionalidades:
        1. Campo reference_cost en product.supplierinfo — precio de lista del proveedor.
        2. Campo reference_cost en product.template — computed automático desde el
           supplierinfo del proveedor principal vigente (menor sequence, fecha válida).
        3. Al crear un nuevo supplierinfo con date_start, se cierran automáticamente
           los registros anteriores del mismo proveedor+producto (date_end = date_start - 1).
        4. Historial inmutable de cambios de reference_cost por proveedor
           (product.supplierinfo.cost.history).
        5. Programación de cambios futuros via product.cost.schedule (crea un nuevo
           supplierinfo con date_start = fecha de vigencia).
        6. Wizard de actualización masiva por categoría, proveedor o selección manual.
        7. Integración con listas de precios de venta: base "Costo de Referencia"
           disponible en reglas de tipo fórmula.
        8. Semáforo de divergencia AVCO vs Costo de Referencia en listado de productos.
        9. Umbrales de divergencia configurables en Ajustes.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'category': 'Inventory/Purchase',
    'depends': [
        'product',
        'purchase',
        'stock',
        'stock_account',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/product_template_views.xml',
        'views/product_supplierinfo_views.xml',
        'views/product_supplierinfo_cost_history_views.xml',
        'views/product_cost_schedule_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/mass_update_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
