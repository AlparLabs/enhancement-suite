from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _is_own_check_payment(self):
        """Verifica si el pago en el wizard corresponde a un cheque propio."""
        self.ensure_one()
        method_code = (
            getattr(self, 'payment_method_code', False)
            or (self.payment_method_line_id and self.payment_method_line_id.code)
            or ''
        )
        return method_code in ('own_checks', 'check_printing')

    @api.onchange('journal_id', 'payment_method_line_id')
    def _onchange_suggest_check_sequence(self):
        """Sugiere el próximo número de cheque en el wizard de registro de pago."""
        for rec in self:
            if rec._is_own_check_payment() and rec.journal_id and rec.journal_id.check_sequence_enabled:
                if not rec.check_number:
                    rec.check_number = rec.journal_id._get_next_check_number_formatted()
