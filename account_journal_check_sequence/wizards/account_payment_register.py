from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _name = 'account.payment.register'
    _inherit = ['account.payment.register', 'account.check.sequence.mixin']

    @api.onchange('journal_id', 'payment_method_line_id')
    def _onchange_suggest_check_sequence(self):
        """Sugiere el próximo número de cheque en el wizard de registro de pago."""
        self._apply_check_sequence_suggestion()

    @api.onchange('l10n_latam_new_check_ids')
    def _onchange_l10n_latam_new_check_ids_suggest_sequence(self):
        """Numera las líneas nuevas de cheques que estén vacías."""
        self._apply_check_sequence_suggestion()


class L10nLatamPaymentRegisterCheck(models.TransientModel):
    _name = 'l10n_latam.payment.register.check'
    _inherit = ['l10n_latam.payment.register.check', 'account.check.sequence.line.mixin']

    _check_sequence_parent_field = 'payment_register_id'
