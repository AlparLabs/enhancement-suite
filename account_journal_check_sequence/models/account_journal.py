import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Separa un número de cheque en prefijo, cuerpo numérico y sufijo
# (ej. 'E-00000100' -> 'E-', '00000100', '').
CHECK_NUMBER_RE = re.compile(r'^(.*?)(\d+)(\D*)$')

DEFAULT_CHECK_NUMBER_PADDING = 8
MAX_CHECK_NUMBER_PADDING = 20


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    check_sequence_enabled = fields.Boolean(
        string='Auto-numerar Cheques Propios',
        default=False,
        help='Si está activo, sugiere automáticamente el próximo número de cheque '
             'al emitir pagos con cheques propios desde este diario.'
    )
    next_check_number = fields.Char(
        string='Próximo Número de Cheque',
        copy=False,
        default='00000001',
        help='Número del siguiente cheque propio a sugerir en pagos u órdenes de pago.'
    )
    check_number_padding = fields.Integer(
        string='Dígitos del Cheque',
        default=DEFAULT_CHECK_NUMBER_PADDING,
        help='Cantidad de dígitos con ceros a la izquierda para formatear el número de cheque (ej. 8 para 00000001).'
    )

    @api.constrains('check_number_padding')
    def _check_check_number_padding(self):
        for journal in self:
            if journal.check_number_padding and not (1 <= journal.check_number_padding <= MAX_CHECK_NUMBER_PADDING):
                raise ValidationError(_(
                    'La cantidad de dígitos del cheque del diario "%(journal)s" debe estar entre 1 y %(maximum)s.',
                    journal=journal.display_name,
                    maximum=MAX_CHECK_NUMBER_PADDING,
                ))

    # -------------------------------------------------------------------------
    # Helpers de parseo / formateo
    # -------------------------------------------------------------------------

    @api.model
    def _parse_check_number(self, value):
        """Descompone un número de cheque.

        :return: tupla ``(prefijo, valor_entero, largo_digitos, sufijo)`` o
            ``None`` si el valor no contiene ninguna parte numérica.
        """
        if not value:
            return None
        match = CHECK_NUMBER_RE.match(str(value).strip())
        if not match:
            return None
        prefix, digits, suffix = match.groups()
        return prefix, int(digits), len(digits), suffix

    def _format_check_number(self, prefix, value, digits_length, suffix):
        """Rearma un número aplicando el padding configurado en el diario."""
        self.ensure_one()
        padding = max(self.check_number_padding or DEFAULT_CHECK_NUMBER_PADDING, digits_length)
        return f"{prefix}{str(value).zfill(padding)}{suffix}"

    # -------------------------------------------------------------------------
    # Cálculo de la secuencia
    # -------------------------------------------------------------------------

    def _get_next_check_number_formatted(self):
        """Devuelve el próximo número formateado según el padding configurado."""
        self.ensure_one()
        parsed = self._parse_check_number(self.next_check_number or '1')
        if not parsed:
            return (self.next_check_number or '').strip()
        return self._format_check_number(*parsed)

    def _calculate_next_number(self, base_number=None):
        """Calcula el siguiente número a partir de un valor base sin persistir nada."""
        self.ensure_one()
        base = base_number or self.next_check_number or '0'
        parsed = self._parse_check_number(base)
        if not parsed:
            return base_number or self.next_check_number
        prefix, value, digits_length, suffix = parsed
        return self._format_check_number(prefix, value + 1, digits_length, suffix)

    def _peek_check_numbers(self, count, start_from=False):
        """Devuelve ``count`` números correlativos sin modificar el contador.

        :param start_from: último número ya usado; si no se indica, se arranca
            desde el próximo número configurado en el diario.
        """
        self.ensure_one()
        numbers = []
        last_number = start_from
        for _index in range(count):
            if last_number:
                last_number = self._calculate_next_number(last_number)
            else:
                last_number = self._get_next_check_number_formatted()
            numbers.append(last_number)
        return numbers

    def _get_highest_check_number(self, numbers):
        """Devuelve el número de mayor valor numérico de la lista recibida."""
        self.ensure_one()
        highest = False
        highest_value = None
        for number in numbers:
            parsed = self._parse_check_number(number)
            if not parsed:
                continue
            if highest_value is None or parsed[1] > highest_value:
                highest_value = parsed[1]
                highest = number
        if highest:
            return highest
        return numbers[-1] if numbers else False

    def _is_check_number_ahead(self, candidate):
        """Indica si ``candidate`` avanza respecto del contador actual.

        Evita que el contador retroceda cuando se postea un pago viejo o un
        cheque con un número inferior al ya alcanzado, lo que llevaría a
        sugerir números duplicados. Si cambia la serie (prefijo o sufijo
        distinto) se asume un cambio de chequera y se acepta el valor.
        """
        self.ensure_one()
        current = self._parse_check_number(self.next_check_number)
        new = self._parse_check_number(candidate)
        if not current or not new:
            return True
        if (current[0], current[3]) != (new[0], new[3]):
            return True
        return new[1] > current[1]

    def _increment_check_number(self, used_number=None):
        """Avanza el contador del diario en base al número efectivamente emitido.

        Se usa ``sudo()`` porque la escritura sobre ``account.journal`` está
        reservada a ``account.group_account_manager`` y quien postea el pago
        puede ser un usuario de Facturación.
        """
        self.ensure_one()
        if not self.check_sequence_enabled:
            return
        candidate = self._calculate_next_number(used_number)
        if not candidate or candidate == self.next_check_number:
            return
        if not self._is_check_number_ahead(candidate):
            _logger.info(
                'Diario %s: se ignora el retroceso de la secuencia de cheques '
                '(actual: %s, calculado: %s).',
                self.display_name, self.next_check_number, candidate,
            )
            return
        self.sudo().next_check_number = candidate
