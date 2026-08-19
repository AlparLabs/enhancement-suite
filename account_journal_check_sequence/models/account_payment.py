from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _is_own_check_payment(self):
        """Verifica si el pago corresponde a la emisión de un cheque propio."""
        self.ensure_one()
        method_code = (
            getattr(self, 'payment_method_code', False)
            or (self.payment_method_line_id and self.payment_method_line_id.code)
            or ''
        )
        return method_code in ('own_checks', 'check_printing')

    def _get_check_number_value(self):
        """Obtiene el número de cheque del pago (soporta check_number o l10n_latam_new_check_ids)."""
        self.ensure_one()
        if hasattr(self, 'check_number') and self.check_number:
            return self.check_number
        if hasattr(self, 'l10n_latam_new_check_ids') and self.l10n_latam_new_check_ids:
            return self.l10n_latam_new_check_ids[:1].name
        return False

    @api.onchange('journal_id', 'payment_method_line_id')
    def _onchange_suggest_check_sequence(self):
        """
        Al seleccionar el diario de banco y método Cheque Propio (en Órdenes de Pago
        de ADHOC o pagos estándar), sugiere el próximo número de cheque configurado en el diario.
        """
        for rec in self:
            if rec._is_own_check_payment() and rec.journal_id and rec.journal_id.check_sequence_enabled:
                next_num = rec.journal_id._get_next_check_number_formatted()
                if hasattr(rec, 'check_number') and not rec.check_number:
                    rec.check_number = next_num
                if hasattr(rec, 'l10n_latam_new_check_ids'):
                    for check in rec.l10n_latam_new_check_ids:
                        if not check.name:
                            check.name = next_num

    def action_post(self):
        """
        Al validar/publicar los pagos (individuales o desde la Orden de Pago de ADHOC),
        actualiza el contador de cheques del diario bancario.
        """
        res = super().action_post()
        for payment in self:
            if (
                payment._is_own_check_payment()
                and payment.journal_id
                and payment.journal_id.check_sequence_enabled
            ):
                chk_num = payment._get_check_number_value()
                if chk_num:
                    payment.journal_id._increment_check_number(chk_num)
        return res
