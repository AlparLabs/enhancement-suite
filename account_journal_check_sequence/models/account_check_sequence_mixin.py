from odoo import models


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

    def _apply_check_sequence_suggestion(self):
        """Completa los números de cheque faltantes con el correlativo del diario.

        Se renumera una línea cuando está vacía o cuando repite un número ya
        usado en otra línea del mismo registro. Ese segundo caso es el que se
        da al agregar una línea en la pestaña Cheques: el valor por defecto
        sale del contador del diario, que no avanza hasta postear el pago, así
        que todas las líneas nuevas nacen con el mismo número.

        Un número distinto cargado por el usuario (por rotura, anulación o
        salto de chequera) siempre se respeta, y el resto de las líneas
        encadena a partir del más alto.
        """
        for rec in self:
            journal = rec._check_sequence_journal()
            if not journal:
                continue
            used_numbers = []
            for check in rec.l10n_latam_new_check_ids:
                if check.name and check.name not in used_numbers:
                    used_numbers.append(check.name)
                    continue
                start_from = journal._get_highest_check_number(used_numbers) if used_numbers else False
                check.name = journal._peek_check_numbers(1, start_from=start_from)[0]
                used_numbers.append(check.name)
