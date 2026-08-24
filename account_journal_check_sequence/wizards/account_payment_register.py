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
    _inherit = 'l10n_latam.payment.register.check'

    @api.model_create_multi
    def create(self, vals_list):
        """Numera los cheques del wizard encadenando el correlativo del diario."""
        assigned_by_register = {}
        for vals in vals_list:
            register_id = vals.get('payment_register_id')
            if not register_id:
                continue
            register = self.env['account.payment.register'].browse(register_id).exists()
            journal = register and register._check_sequence_journal()
            if not journal:
                continue
            if register.id not in assigned_by_register:
                assigned_by_register[register.id] = [
                    check.name for check in register.l10n_latam_new_check_ids if check.name
                ]
            already_used = assigned_by_register[register.id]
            if vals.get('name'):
                already_used.append(vals['name'])
                continue
            start_from = journal._get_highest_check_number(already_used) if already_used else False
            vals['name'] = journal._peek_check_numbers(1, start_from=start_from)[0]
            already_used.append(vals['name'])
        return super().create(vals_list)
