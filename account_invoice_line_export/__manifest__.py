{
    'name': 'Invoice Line Export',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Export invoice and sale lines as flat Excel with full header data per row',
    'description': """
        Generates denormalized Excel exports for:
        - Customer Invoices & Credit Notes
        - Vendor Bills & Credit Notes
        - Sale Orders
        Each row repeats all header-level data alongside its invoice/sale line.

        Custom fields expected (created via Odoo Studio):
        - res.company: x_studio_empresa, x_studio_sucursal
        - res.partner: x_studio_tipo_cliente, x_studio_equipo_de_ventas
        - sale.order: x_studio_pipedrive_id
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'depends': ['account', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/invoice_line_export_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
