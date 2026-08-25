from odoo import api, fields, models


class AccountCheckSequenceMixin(models.AbstractModel):
    """Lógica compartida entre account.payment y account.payment.register.

    El alcance del módulo es el método de pago `own_checks` de
    `l10n_latam_check`: la chequera nativa de Odoo (`account_check_printing`,
    método `check_printing`) no contempla los cheques LATAM (diferidos,
    echeqs), que es el motivo por el que existe este módulo. Ambas
    numeraciones son independientes y no se pisan.

    Los dos modelos exponen los mismos campos relevantes (`journal_id`,
    `payment_method_line_id` y `l10n_latam_new_check_ids`), así que la
    sugerencia de número se resuelve una sola vez acá.
    """

    _name = 'account.check.sequence.mixin'
    _description = 'Sugerencia de numeración de cheques propios'

    check_sequence_next_number = fields.Char(
        string='Próximo Número de Cheque Sugerido',
        compute='_compute_check_sequence_next_number',
        help='Campo técnico: próximo número libre de la chequera, considerando las '
             'líneas de cheque ya cargadas. Las vistas lo pasan por el contexto de la '
             'One2many para que cada línea nueva nazca con el número correcto.',
    )

    def _is_own_check_payment(self):
        """Indica si el registro emite cheques propios LATAM."""
        self.ensure_one()
        return self.payment_method_line_id.code == 'own_checks'

    def _check_sequence_journal(self):
        """Diario habilitado para autonumerar, o un recordset vacío."""
        self.ensure_one()
        journal = self.journal_id
        if journal and journal.check_sequence_enabled and self._is_own_check_payment():
            return journal
        return self.env['account.journal']

    def _get_check_numbers_used(self):
        """Números de cheque efectivamente cargados en el registro."""
        self.ensure_one()
        return [check.name for check in self.l10n_latam_new_check_ids if check.name]

    @api.depends(
        'journal_id.check_sequence_enabled', 'journal_id.next_check_number',
        'payment_method_line_id', 'l10n_latam_new_check_ids.name',
    )
    def _compute_check_sequence_next_number(self):
        for rec in self:
            journal = rec._check_sequence_journal()
            if not journal:
                rec.check_sequence_next_number = False
                continue
            used_numbers = rec._get_check_numbers_used()
            start_from = journal._get_highest_check_number(used_numbers) if used_numbers else False
            rec.check_sequence_next_number = journal._peek_check_numbers(1, start_from=start_from)[0]

    def _apply_check_sequence_suggestion(self):
        """Completa los números de cheque faltantes con el correlativo del diario.

        Las líneas tipeadas por el usuario son anclas fijas: se respetan tal
        cual y el resto encadena a partir de ellas. Una línea es del usuario
        cuando tiene número y ese número ya no coincide con
        ``autofilled_check_number``, es decir apenas la edita.

        Todo lo demás (vacío o autocompletado por el módulo) se recalcula en
        cada pasada. Por eso una línea autocompletada sigue al salto que el
        usuario haga más arriba: si cambia la primera de 00001001 a 00001050
        porque arrancó otra chequera, la siguiente pasa a 00001051. Y por eso
        se corrige sola si quedó repitiendo el número de otra.
        """
        for rec in self:
            journal = rec._check_sequence_journal()
            if not journal:
                continue
            used_numbers = []
            for check in rec.l10n_latam_new_check_ids:
                is_autofilled = check.name and check.name == check.autofilled_check_number
                if check.name and not is_autofilled:
                    used_numbers.append(check.name)
                    continue
                start_from = journal._get_highest_check_number(used_numbers) if used_numbers else False
                check.name = journal._peek_check_numbers(1, start_from=start_from)[0]
                check.autofilled_check_number = check.name
                used_numbers.append(check.name)
