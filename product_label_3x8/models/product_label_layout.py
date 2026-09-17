from odoo import fields, models


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[
            ('3x8xprice', '3 x 8 (65x35mm)'),
            ('3x8xpromo', '3 x 8 Promoción / Descuento (65x35mm)'),
        ],
        ondelete={
            '3x8xprice': 'set default',
            '3x8xpromo': 'set default',
        },
    )
    loyalty_program_id = fields.Many2one(
        'loyalty.program',
        string="Promoción (Loyalty)",
        domain="[('active', '=', True)]",
        help="Programa de Loyalty aplicable para calcular los precios de oferta.",
    )
    promo_discount = fields.Float(
        string="Descuento manual (%)",
        help="Porcentaje de descuento directo a aplicar si no se selecciona programa de Loyalty.",
    )

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        if self.print_format in ('3x8xprice', '3x8xpromo'):
            xml_id = 'product_label_3x8.report_product_template_label_3x8'
            data['price_included'] = True
            data['is_promo'] = (self.print_format == '3x8xpromo')
            data['loyalty_program_id'] = self.loyalty_program_id.id if self.loyalty_program_id else False
            data['promo_discount'] = self.promo_discount
        return xml_id, data
