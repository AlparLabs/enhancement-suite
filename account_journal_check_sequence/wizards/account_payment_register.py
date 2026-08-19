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
        """Sugiere el próximo número de cheque al agregar líneas en el wizard."""
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


class L10nLatamPaymentRegisterCheck(models.TransientModel):
    _inherit = 'l10n_latam.payment.register.check'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('payment_register_id'):
                reg = self.env['account.payment.register'].browse(vals['payment_register_id'])
                if reg._is_own_check_payment() and reg.journal_id and reg.journal_id.check_sequence_enabled:
                    vals['name'] = reg.journal_id._get_next_check_number_formatted()
        return super().create(vals_list)
