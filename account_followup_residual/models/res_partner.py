from odoo import models
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_unreconciled_aml_domain(self):
        # Exclude lines whose invoice is already paid or reversed to prevent them
        # from showing as outstanding when the move.line is technically unreconciled
        # at DB level (e.g. FX writeoff edge cases, data integrity issues).
        return super()._get_unreconciled_aml_domain() & Domain(
            'move_id.payment_state', 'not in', ('paid', 'reversed')
        )
