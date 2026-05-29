{
    'name': 'AlparData - Costo de Referencia Comercial',
    'version': '19.0.1.0.0',
    'summary': 'Doble precio de costo: AVCO contable + costo de referencia comercial estable',
    'description': """
        Módulo desarrollado por AlparData para Grupo Broda.

        Problema que resuelve:
        - En Odoo con AVCO, cada recepción de mercadería mueve el standard_price
          automáticamente via stock.valuation.layer.
        - Esto hace que el margen calculado en listas de precios y BOM fluctúe
          con cada compra, lo cual es inaceptable para Retail (FRAT).
        - La solución: separar el costo contable (AVCO real) del costo comercial
          (reference_cost) que se usa para margen y precio de venta.

        Funcionalidades:
        1. Campo reference_cost en product.template — costo comercial estable.
        2. Programación de cambios futuros de reference_cost (product.cost.schedule).
        3. Cron job diario que aplica programaciones cuya fecha_vigencia <= hoy.
        4. Wizard de actualización masiva por categoría o proveedor.
        5. Soporte multi-empresa: reference_cost por company_id.
        6. Historial de cambios de reference_cost (product.cost.history).
        7. Vista de semáforo en listado de productos: detecta cuando AVCO diverge
           más de un umbral configurable del reference_cost.
        8. Integración con listas de precios: opción "Costo de Referencia"
           como base en reglas de tipo fórmula (product.pricelist.item).
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
        'views/product_cost_schedule_views.xml',
        'views/product_cost_history_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/mass_update_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
