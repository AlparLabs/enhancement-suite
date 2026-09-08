{
    'name': 'Website Sale Product Channel UX',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Gestión visual y asignación masiva de canales de venta web (Franquicias / Distribución)',
    'description': """
        Módulo UX de Canales de Producto para EntreDos:
        - Visualización del canal web (sitio) en la vista de lista de productos.
        - Filtros y agrupación rápida por canal en la búsqueda de productos.
        - Asistente masivo para asignar productos a un canal específico o a ambos canales.
        - Información contextual en el formulario del producto.
    """,
    'author': 'AlparData',
    'website': 'https://alpardata.com.ar',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/product_channel_assign_wizard_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
