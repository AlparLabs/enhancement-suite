from odoo import api, models


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'account.check.sequence.mixin']

    @api.onchange('journal_id', 'payment_method_line_id')
    def _onchange_suggest_check_sequence(self):
        """Sugiere el próximo número al elegir diario y método Cheque Propio.

        Aplica tanto a los pagos estándar como a los generados desde las
        Órdenes de Pago de ADHOC, que terminan creando account.payment.
        """
        self._apply_check_sequence_suggestion()

    @api.onchange('l10n_latam_new_check_ids')
    def _onchange_l10n_latam_new_check_ids_suggest_sequence(self):
        """Numera las líneas nuevas de la pestaña Cheques que estén vacías."""
        self._apply_check_sequence_suggestion()

    def action_post(self):
        """Actualiza el contador de la chequera con el número más alto emitido."""
        res = super().action_post()
        for payment in self:
            checkbook = payment._check_sequence_checkbook()
            if not checkbook:
                continue
            used_numbers = payment._get_check_numbers_used()
            if used_numbers:
                checkbook._increment_check_number(checkbook._get_highest_check_number(used_numbers))
        return res
