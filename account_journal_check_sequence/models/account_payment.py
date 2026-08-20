from odoo import models


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'account.journal.check.sequence.mixin']

    def _get_check_numbers_used(self):
        """Devuelve una lista con todos los números de cheque utilizados en este pago."""
        self.ensure_one()
        numbers = [chk.name for chk in self.l10n_latam_new_check_ids if chk.name]
        if 'check_number' in self._fields and self.check_number:
            numbers.append(self.check_number)
        return numbers

    def action_post(self):
        """
        Al validar/publicar los pagos (individuales o desde la Orden de Pago de ADHOC),
        actualiza el contador de cheques del diario bancario con el número más alto utilizado.
        """
        res = super().action_post()
        for payment in self:
            if not payment._use_check_sequence():
                continue
            highest = payment.journal_id._get_highest_check_number(
                payment._get_check_numbers_used()
            )
            if highest:
                payment.journal_id._increment_check_number(highest)
        return res
