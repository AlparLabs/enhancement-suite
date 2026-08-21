from odoo import api, fields, models

from ..models.check_sequence_mixin import get_check_number_from_context


class AccountPaymentRegister(models.TransientModel):
    _name = 'account.payment.register'
    _inherit = ['account.payment.register', 'account.journal.check.sequence.mixin']


class L10nLatamPaymentRegisterCheck(models.TransientModel):
    _inherit = 'l10n_latam.payment.register.check'

    autofilled_check_number = fields.Char(
        string='Número Autocompletado',
        help='Campo técnico: último número asignado automáticamente por la chequera del diario.'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'name' in fields_list and not res.get('name'):
            number = get_check_number_from_context(self.env)
            if number:
                res['name'] = number
                res['autofilled_check_number'] = number
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # Igual que en l10n_latam.check: hay que avanzar el correlativo dentro
        # del propio batch para no repetir el número en todas las líneas.
        last_by_journal = {}
        for vals in vals_list:
            if vals.get('name') or not vals.get('payment_register_id'):
                continue
            register_id = vals['payment_register_id']
            if not isinstance(register_id, int):
                continue
            reg = self.env['account.payment.register'].browse(register_id).exists()
            if not reg or not reg._use_check_sequence():
                continue
            journal = reg.journal_id
            number = journal._next_check_number_for_batch(last_by_journal.get(journal.id))
            vals['name'] = number
            vals['autofilled_check_number'] = number
            last_by_journal[journal.id] = number
        return super().create(vals_list)
