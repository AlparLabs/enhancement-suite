from odoo import api, fields, models


class L10nLatamCheck(models.Model):
    _name = 'l10n_latam.check'
    _inherit = ['l10n_latam.check', 'account.check.sequence.line.mixin']

    _check_sequence_parent_field = 'payment_id'

    checkbook_id = fields.Many2one(
        'account.checkbook',
        string='Chequera',
        readonly=True,
        copy=False,
        index=True,
        help='Chequera de la que se emitió el cheque. Se completa al publicar el pago y '
             'se usa para detectar números repetidos entre diarios que comparten chequera.',
    )

    @api.onchange('payment_id')
    def _onchange_payment_id_suggest_check_sequence(self):
        for rec in self.filtered(lambda check: not check.name):
            payment = rec.payment_id or rec._resolve_check_sequence_parent()
            number = payment and rec._get_next_check_number_for_line(payment)
            if number:
                rec.name = number
                rec.autofilled_check_number = number
