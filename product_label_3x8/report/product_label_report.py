from odoo import models
from odoo.addons.product.report.product_label_report import _prepare_data


class ReportProductTemplateLabel3x8(models.AbstractModel):
    _name = 'report.product_label_3x8.report_producttemplatelabel3x8'
    _description = 'Product Label Report 3x8'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)
