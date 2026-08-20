import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Separa un número de cheque en prefijo, dígitos y sufijo. El prefijo es
# perezoso, de modo que se toma siempre el último grupo numérico del string
# (ej. 'AB12CD34' -> prefijo 'AB12CD', dígitos '34').
CHECK_NUMBER_RE = re.compile(r'^(.*?)(\d+)(\D*)$')


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    check_sequence_enabled = fields.Boolean(
        string='Auto-numerar Cheques Propios',
        default=False,
        help='Si está activo, sugiere automáticamente el próximo número de cheque '
             'al emitir pagos con cheques propios de la localización (método '
             '"Cheques propios") desde este diario. No aplica al flujo estándar de '
             'impresión de cheques, que se numera con "Numeración manual de cheques".'
    )
    next_check_number = fields.Char(
        string='Próximo Número de Cheque',
        copy=False,
        default='00000001',
        tracking=True,
        help='Número del siguiente cheque propio a sugerir en pagos u órdenes de pago.'
    )
    check_number_padding = fields.Integer(
        string='Dígitos del Cheque',
        default=8,
        help='Cantidad de dígitos con ceros a la izquierda para formatear el número de cheque '
             '(ej. 8 para 00000001). Mínimo 8: l10n_latam_check completa con ceros hasta 8 '
             'dígitos al escribir el número, así que un padding menor quedaría desalineado '
             'con el número realmente guardado en el cheque.'
    )

    @api.constrains('check_number_padding')
    def _check_check_number_padding(self):
        """El padding no puede ser menor a 8.

        ``l10n_latam.check._onchange_name`` (y su equivalente en el wizard) hacen
        ``name.zfill(8)``: con un padding menor, el número guardado en el cheque
        no coincidiría con el que lleva el contador del diario.
        """
        for journal in self:
            if journal.check_sequence_enabled and journal.check_number_padding < 8:
                raise ValidationError(_(
                    'Los dígitos del cheque del diario "%s" no pueden ser menos de 8: '
                    'la localización completa los números con ceros hasta 8 dígitos.',
                    journal.display_name,
                ))

    @api.constrains('check_sequence_enabled')
    def _check_no_double_check_numbering(self):
        """Impide convivir con la numeración nativa de impresión de cheques.

        ``account_check_printing`` ya numera los cheques del método
        ``check_printing`` con su propia ``ir.sequence``. Tener las dos activas
        en el mismo diario deja dos contadores independientes sobre la misma
        chequera física.
        """
        if 'check_manual_sequencing' not in self._fields:
            return
        for journal in self:
            if journal.check_sequence_enabled and journal.check_manual_sequencing:
                raise ValidationError(_(
                    'El diario "%s" ya usa la numeración manual de cheques de Odoo. '
                    'Desactive "Numeración manual de cheques" o '
                    '"Auto-numerar Cheques Propios": no pueden convivir sobre la '
                    'misma chequera.',
                    journal.display_name,
                ))

    def _split_check_number(self, number):
        """Descompone un número de cheque en (prefijo, valor, sufijo, dígitos).

        Devuelve False si el string no contiene ninguna parte numérica.
        """
        match = CHECK_NUMBER_RE.match(str(number or '').strip())
        if not match:
            return False
        prefix, digits_str, suffix = match.groups()
        return prefix, int(digits_str), suffix, len(digits_str)

    def _format_check_number(self, prefix, value, suffix, digits=0):
        """Formatea las partes de un número aplicando el padding del diario."""
        self.ensure_one()
        padding = max(self.check_number_padding or 8, digits)
        return f"{prefix}{str(value).zfill(padding)}{suffix}"

    def _get_next_check_number_formatted(self):
        """Devuelve el próximo número formateado según el padding configurado."""
        self.ensure_one()
        parts = self._split_check_number(self.next_check_number or '1')
        if not parts:
            return (self.next_check_number or '').strip()
        prefix, value, suffix, digits = parts
        return self._format_check_number(prefix, value, suffix, digits)

    def _calculate_next_number(self, base_number=None):
        """Calcula el siguiente número a partir de un valor base sin modificar el diario."""
        self.ensure_one()
        base = base_number if base_number else self.next_check_number
        parts = self._split_check_number(base)
        if not parts:
            return base_number or self.next_check_number
        prefix, value, suffix, digits = parts
        return self._format_check_number(prefix, value + 1, suffix, digits)

    def _get_highest_check_number(self, numbers):
        """Devuelve el mayor de una lista de números de cheque.

        La comparación es numérica sobre el grupo de dígitos: el orden de la
        lista (o de una One2many) no es confiable para decidir cuál fue el
        último cheque emitido.
        """
        self.ensure_one()
        highest = False
        highest_value = None
        for number in numbers or []:
            parts = self._split_check_number(number)
            if not parts:
                continue
            if highest_value is None or parts[1] > highest_value:
                highest, highest_value = number, parts[1]
        return highest

    def _increment_check_number(self, used_number=None):
        """Avanza la secuencia del diario en base al número efectivamente utilizado.

        La secuencia nunca retrocede: si el número usado es menor o igual al
        que ya tiene el diario (reemisión de un cheque viejo, re-publicación de
        un pago que ya avanzó el contador), no se toca nada.
        """
        self.ensure_one()
        if not self.check_sequence_enabled:
            return
        # Bloqueamos la fila del diario para que dos pagos publicados en
        # paralelo no calculen el próximo número sobre el mismo valor.
        current = self._lock_and_read_next_check_number()
        candidate = self._calculate_next_number(used_number)
        current_parts = self._split_check_number(current)
        candidate_parts = self._split_check_number(candidate)
        if current_parts and candidate_parts and candidate_parts[1] <= current_parts[1]:
            return
        self.next_check_number = candidate

    def _lock_and_read_next_check_number(self):
        """Toma un lock exclusivo sobre el diario y devuelve el valor en base."""
        self.ensure_one()
        self.flush_recordset(['next_check_number'])
        self.env.cr.execute(
            'SELECT next_check_number FROM account_journal WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        value = row[0] if row else False
        self.invalidate_recordset(['next_check_number'])
        return value

    def _assign_check_numbers(self, checks, force_all=False):
        """Completa el número de las líneas de cheque con valores correlativos.

        Respeta los números cargados a mano. Con ``force_all=True`` (cambio de
        diario o de método de pago) también recalcula los que había asignado
        automáticamente este módulo, para que no queden números de la chequera
        anterior.
        """
        self.ensure_one()
        if not self.check_sequence_enabled:
            return
        last_number = False
        for check in checks:
            autofilled = check.name and check.name == check.autofilled_check_number
            if check.name and not (force_all and autofilled):
                last_number = check.name
                continue
            number = self._calculate_next_number(last_number) if last_number \
                else self._get_next_check_number_formatted()
            check.name = number
            check.autofilled_check_number = number
            last_number = number

    def _next_check_number_for_batch(self, last_number=None):
        """Próximo número a usar dentro de un mismo ``create`` multi-registro."""
        self.ensure_one()
        if not last_number:
            return self._get_next_check_number_formatted()
        return self._calculate_next_number(last_number)
