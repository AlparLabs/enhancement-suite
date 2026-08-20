from odoo import api, fields, models

from .check_sequence_mixin import get_check_number_from_context


class L10nLatamCheck(models.Model):
    _inherit = 'l10n_latam.check'

    autofilled_check_number = fields.Char(
        string='Número Autocompletado',
        copy=False,
        help='Campo técnico: último número asignado automáticamente por la chequera del '
             'diario. Si el usuario edita el número, deja de coincidir y el módulo pasa a '
             'respetar el valor cargado a mano.'
    )

    def _get_check_sequence_payment(self, payment_id=None):
        """Devuelve el pago desde el que se debe tomar la chequera, si aplica."""
        payment_id = payment_id or self.payment_id.id
        # En un onchange sobre un registro nuevo el id puede ser un NewId: no hay
        # pago persistido del que tomar la chequera.
        if not isinstance(payment_id, int):
            return self.env['account.payment']
        payment = self.env['account.payment'].browse(payment_id).exists()
        if payment and payment._use_check_sequence():
            return payment
        return self.env['account.payment']

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'name' in fields_list and not res.get('name'):
            # Camino principal: el diario viene en el contexto de la O2M.
            number = get_check_number_from_context(self.env)
            if not number:
                payment_id = res.get('payment_id') or self.env.context.get('default_payment_id')
                if not payment_id and self.env.context.get('active_model') == 'account.payment':
                    # active_id sólo es un pago si el modelo activo lo es: en el
                    # wizard de registro, por ejemplo, apunta a un account.move.
                    payment_id = self.env.context.get('active_id')
                payment = self._get_check_sequence_payment(payment_id)
                if payment:
                    number = payment.journal_id._get_next_check_number_formatted()
            if number:
                res['name'] = number
                res['autofilled_check_number'] = number
        return res

    @api.onchange('payment_id')
    def _onchange_payment_id_suggest_check_sequence(self):
        for rec in self:
            if rec.name:
                continue
            payment = rec._get_check_sequence_payment(
                rec.payment_id.id or rec.env.context.get('default_payment_id')
            )
            if payment:
                number = payment.journal_id._get_next_check_number_formatted()
                rec.name = number
                rec.autofilled_check_number = number

    @api.model_create_multi
    def create(self, vals_list):
        # Un mismo create puede traer varias líneas sin número (duplicar un pago,
        # importar, guardar una One2many con varias líneas nuevas): hay que avanzar
        # el correlativo dentro del batch o todas quedarían con el mismo número.
        last_by_journal = {}
        for vals in vals_list:
            if vals.get('name') or not vals.get('payment_id'):
                continue
            payment = self._get_check_sequence_payment(vals['payment_id'])
            if not payment:
                continue
            journal = payment.journal_id
            number = journal._next_check_number_for_batch(last_by_journal.get(journal.id))
            vals['name'] = number
            vals['autofilled_check_number'] = number
            last_by_journal[journal.id] = number
        return super().create(vals_list)
