from odoo import _, api, models


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
        """Publica serializando por chequera y avanza el contador.

        El lock de las chequeras se toma antes de ``super()`` porque ahí adentro
        corre el control de números duplicados (ver
        ``_get_blocking_l10n_latam_warning_msg``). Si se tomara después, dos
        pagos concurrentes con el mismo número pasarían el control los dos.
        """
        checkbooks = self.env['account.checkbook']
        for payment in self:
            checkbooks |= payment._check_sequence_checkbook()
        checkbooks._lock_checkbooks()
        res = super().action_post()
        for payment in self:
            checkbook = payment._check_sequence_checkbook()
            if not checkbook:
                continue
            payment.l10n_latam_new_check_ids.write({'checkbook_id': checkbook.id})
            used_numbers = payment._get_check_numbers_used()
            if used_numbers:
                checkbook._increment_check_number(checkbook._get_highest_check_number(used_numbers))
        return res

    def _get_blocking_l10n_latam_warning_msg(self):
        """Suma los números de cheque ya usados en la chequera.

        El método nativo alimenta la alerta del formulario
        (``l10n_latam_check_warning_msg``) y el ``ValidationError`` de
        ``action_post``, así que con esto se cubren las dos cosas. El índice
        único nativo es por línea de método de pago, es decir por diario: no
        ve duplicados entre diarios que comparten chequera.
        """
        msgs = super()._get_blocking_l10n_latam_warning_msg()
        for rec in self.filtered(lambda payment: payment.state == 'draft'):
            msgs.extend(rec._get_checkbook_duplicate_msgs())
        return msgs

    def _get_checkbook_duplicate_msgs(self):
        """Mensajes por cada número repetido en el pago o ya emitido en la chequera.

        Cuenta todo cheque de la chequera cuyo pago no esté en borrador ni
        cancelado, incluidos los anulados: ese número ya se usó en papel. Se
        busca con ``sudo()`` porque la chequera puede estar compartida entre
        compañías y los cheques de otra compañía no son visibles para el
        usuario, pero igual ocupan el número.
        """
        self.ensure_one()
        checkbook = self._check_sequence_checkbook()
        names = self._get_check_numbers_used()
        if not checkbook or not names:
            return []
        msgs = [
            _('El cheque %(number)s está cargado más de una vez en este pago.', number=name)
            for name in sorted({name for name in names if names.count(name) > 1})
        ]
        used_checks = self.env['l10n_latam.check'].sudo().search([
            ('checkbook_id', '=', checkbook.id),
            ('name', 'in', list(set(names))),
            ('payment_id.state', 'not in', ('draft', 'canceled')),
            ('id', 'not in', self.l10n_latam_new_check_ids._origin.ids),
        ], order='name, id')
        for check in used_checks:
            msgs.append(_(
                'El cheque %(number)s de la chequera «%(checkbook)s» ya fue emitido en '
                '%(payment)s (diario %(journal)s).',
                number=check.name,
                checkbook=checkbook.name,
                payment=check.payment_id.display_name,
                journal=check.payment_id.journal_id.display_name,
            ))
        return msgs
