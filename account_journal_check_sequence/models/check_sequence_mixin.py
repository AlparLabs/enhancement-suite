from odoo import api, models

# Métodos de pago considerados "cheque propio":
#   - own_checks: cheques propios de la localización (l10n_latam_check),
#     numerados en las líneas de l10n_latam_new_check_ids.
#   - check_printing: flujo estándar de impresión de cheques, numerado en el
#     campo check_number del pago.
# Odoo tiene numeración propia para check_printing (check_manual_sequencing /
# check_next_number en el diario). Este módulo sólo interviene si esa
# numeración nativa está desactivada; la constraint
# account.journal._check_no_double_check_numbering impide que convivan.
OWN_CHECK_METHOD_CODES = ('own_checks', 'check_printing')


def get_check_number_from_context(env):
    """Próximo número de chequera segun el contexto de la O2M de cheques.

    Las vistas del pago y del wizard pasan ``check_sequence_journal_id`` y
    ``check_sequence_method_code`` del padre en el contexto del campo
    ``l10n_latam_new_check_ids``. Asi ``default_get`` puede numerar la linea
    nueva apenas se agrega, sin depender de ``active_id``: ese id no siempre
    corresponde a un pago (en el wizard de registro apunta a un account.move)
    y browsearlo a ciegas puede traer el numero de otra chequera.
    """
    journal_id = env.context.get('check_sequence_journal_id')
    method_code = env.context.get('check_sequence_method_code')
    if not isinstance(journal_id, int) or method_code not in OWN_CHECK_METHOD_CODES:
        return False
    journal = env['account.journal'].browse(journal_id).exists()
    if not journal or not journal.check_sequence_enabled:
        return False
    return journal._get_next_check_number_formatted()


class CheckSequenceMixin(models.AbstractModel):
    """Lógica de chequera compartida entre el pago y el wizard de registro.

    ``account.payment`` y ``account.payment.register`` exponen los mismos
    campos relevantes (``journal_id``, ``payment_method_line_id``,
    ``payment_method_code`` y ``l10n_latam_new_check_ids``), aunque la One2many
    apunte a modelos distintos (``l10n_latam.check`` y
    ``l10n_latam.payment.register.check``). Ambos modelos de cheque tienen
    ``name`` y ``autofilled_check_number``, que es todo lo que necesita
    ``account.journal._assign_check_numbers()``.
    """

    _name = 'account.journal.check.sequence.mixin'
    _description = 'Numeración de chequera por diario'

    def _is_own_check_payment(self):
        """Verifica si corresponde a la emisión de un cheque propio."""
        self.ensure_one()
        return (self.payment_method_code or '') in OWN_CHECK_METHOD_CODES

    def _use_check_sequence(self):
        """Debe tomar números de la chequera configurada en el diario."""
        self.ensure_one()
        return bool(
            self._is_own_check_payment()
            and self.journal_id
            and self.journal_id.check_sequence_enabled
        )

    @api.onchange('journal_id', 'payment_method_line_id')
    def _onchange_suggest_check_sequence(self):
        """Sugiere el próximo número de cheque del diario seleccionado.

        Como cambió el diario (o el método de pago), se recalculan también las
        líneas que este módulo había numerado antes: de lo contrario quedarían
        números de otra chequera. Los cargados a mano se respetan.
        """
        for rec in self:
            if not rec._use_check_sequence():
                continue
            # check_number sólo existe en account.payment (lo agrega
            # account_check_printing), no en account.payment.register.
            if 'check_number' in rec._fields and not rec.check_number:
                rec.check_number = rec.journal_id._get_next_check_number_formatted()
            rec.journal_id._assign_check_numbers(
                rec.l10n_latam_new_check_ids, force_all=True
            )

    @api.onchange('l10n_latam_new_check_ids')
    def _onchange_l10n_latam_new_check_ids_suggest_sequence(self):
        """Renumera correlativamente las líneas de la pestaña Cheques.

        Va con ``force_all=True`` a propósito: ``default_get`` sugiere el mismo
        número para cada línea nueva (no conoce a las hermanas que todavía sólo
        existen en el cliente), así que agregar dos líneas seguidas deja el
        número repetido. Reasignando todo lo autocompletado, esa sugerencia se
        corrige sola. Lo cargado a mano se sigue respetando.
        """
        for rec in self:
            if rec._use_check_sequence():
                rec.journal_id._assign_check_numbers(
                    rec.l10n_latam_new_check_ids, force_all=True
                )
