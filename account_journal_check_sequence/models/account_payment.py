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

    def _get_check_numbers_used(self):
        """Devuelve una lista con todos los números de cheque utilizados en este pago."""
        self.ensure_one()
        numbers = []
        if hasattr(self, 'check_number') and self.check_number:
            numbers.append(self.check_number)
        if hasattr(self, 'l10n_latam_new_check_ids') and self.l10n_latam_new_check_ids:
            numbers.extend([chk.name for chk in self.l10n_latam_new_check_ids if chk.name])
        return numbers

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
                    last_num = False
                    for check in rec.l10n_latam_new_check_ids:
                        if not check.name:
                            calc_num = next_num if not last_num else rec.journal_id._calculate_next_number(last_num)
                            check.name = calc_num
                            last_num = calc_num
                        else:
                            last_num = check.name

    @api.onchange('l10n_latam_new_check_ids')
    def _onchange_l10n_latam_new_check_ids_suggest_sequence(self):
        """
        Al agregar o modificar líneas en la pestaña Cheques, sugiere automáticamente
        el próximo número correlativo para las líneas que no tengan número asignado.
        """
        for rec in self:
            if rec._is_own_check_payment() and rec.journal_id and rec.journal_id.check_sequence_enabled:
                last_num = False
                for check in rec.l10n_latam_new_check_ids:
                    if check.name:
                        last_num = check.name
                    else:
                        if not last_num:
                            next_num = rec.journal_id._get_next_check_number_formatted()
                        else:
                            next_num = rec.journal_id._calculate_next_number(last_num)
                        check.name = next_num
                        last_num = next_num

    def action_post(self):
        """
        Al validar/publicar los pagos (individuales o desde la Orden de Pago de ADHOC),
        actualiza el contador de cheques del diario bancario con el número más alto utilizado.
        """
        res = super().action_post()
        for payment in self:
            if (
                payment._is_own_check_payment()
                and payment.journal_id
                and payment.journal_id.check_sequence_enabled
            ):
                used_numbers = payment._get_check_numbers_used()
                if used_numbers:
                    # Incrementamos a partir del último número utilizado en la lista
                    last_number = used_numbers[-1]
                    payment.journal_id._increment_check_number(last_number)
        return res
