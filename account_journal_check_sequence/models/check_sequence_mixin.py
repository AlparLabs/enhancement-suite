from odoo import api, models

# Sólo el método de cheque propio de la localización (l10n_latam_check).
# El flujo estándar 'check_printing' queda deliberadamente fuera: Odoo ya lo
# numera con check_manual_sequencing / check_next_number en el diario.
OWN_CHECK_METHOD_CODES = ('own_checks',)


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
            if rec._use_check_sequence():
                rec.journal_id._assign_check_numbers(
                    rec.l10n_latam_new_check_ids, force_all=True
                )

    @api.onchange('l10n_latam_new_check_ids')
    def _onchange_l10n_latam_new_check_ids_suggest_sequence(self):
        """Numera las líneas nuevas de la pestaña Cheques que estén vacías."""
        for rec in self:
            if rec._use_check_sequence():
                rec.journal_id._assign_check_numbers(rec.l10n_latam_new_check_ids)
