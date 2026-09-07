from odoo import fields, models


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[('3x8xprice', '3 x 8 (65x35mm)')],
        ondelete={'3x8xprice': 'set default'},
    )

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        if self.print_format == '3x8xprice':
            xml_id = 'product_label_3x8.report_product_template_label_3x8'
        return xml_id, data
