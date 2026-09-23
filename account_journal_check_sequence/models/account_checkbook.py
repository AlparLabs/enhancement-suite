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


class AccountCheckbook(models.Model):
    """Chequera de cheques propios.

    Tiene el contador que antes vivía en cada diario de banco. Varios diarios
    pueden apuntar a la misma chequera y consumen un único correlativo; si
    ``company_id`` está vacío, esos diarios pueden ser de compañías distintas.
    """

    _name = 'account.checkbook'
    _description = 'Chequera'
    _order = 'name, id'

    name = fields.Char(string='Nombre', required=True)
    next_number = fields.Char(
        string='Próximo Número de Cheque',
        copy=False,
        default='00000001',
        help='Número del siguiente cheque propio a sugerir en pagos u órdenes de pago.',
    )
    padding = fields.Integer(
        string='Dígitos del Cheque',
        default=DEFAULT_CHECK_NUMBER_PADDING,
        help='Cantidad de dígitos con ceros a la izquierda para formatear el número de cheque (ej. 8 para 00000001).',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        help='Vacío: la chequera se puede compartir entre diarios de distintas compañías.',
    )
    journal_ids = fields.One2many(
        'account.journal',
        'checkbook_id',
        string='Diarios',
        readonly=True,
        help='Diarios de banco que numeran sus cheques propios con esta chequera.',
    )
    active = fields.Boolean(default=True)

    @api.constrains('padding')
    def _check_padding(self):
        for checkbook in self:
            if checkbook.padding and not (1 <= checkbook.padding <= MAX_CHECK_NUMBER_PADDING):
                raise ValidationError(_(
                    'La cantidad de dígitos de la chequera "%(checkbook)s" debe estar entre 1 y %(maximum)s.',
                    checkbook=checkbook.display_name,
                    maximum=MAX_CHECK_NUMBER_PADDING,
                ))

    @api.constrains('company_id')
    def _check_company_journals(self):
        # sudo: los diarios de compañías no activas también tienen que coincidir.
        self.sudo().journal_ids._check_checkbook_company()

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
        """Rearma un número aplicando el padding configurado en la chequera."""
        self.ensure_one()
        padding = max(self.padding or DEFAULT_CHECK_NUMBER_PADDING, digits_length)
        return f"{prefix}{str(value).zfill(padding)}{suffix}"

    # -------------------------------------------------------------------------
    # Cálculo de la secuencia
    # -------------------------------------------------------------------------

    def _get_next_check_number_formatted(self):
        """Devuelve el próximo número formateado según el padding configurado."""
        self.ensure_one()
        parsed = self._parse_check_number(self.next_number or '1')
        if not parsed:
            return (self.next_number or '').strip()
        return self._format_check_number(*parsed)

    def _calculate_next_number(self, base_number=None):
        """Calcula el siguiente número a partir de un valor base sin persistir nada."""
        self.ensure_one()
        base = base_number or self.next_number or '0'
        parsed = self._parse_check_number(base)
        if not parsed:
            return base_number or self.next_number
        prefix, value, digits_length, suffix = parsed
        return self._format_check_number(prefix, value + 1, digits_length, suffix)

    def _peek_check_numbers(self, count, start_from=False):
        """Devuelve ``count`` números correlativos sin modificar el contador.

        :param start_from: último número ya usado; si no se indica, se arranca
            desde el próximo número configurado en la chequera.
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
        current = self._parse_check_number(self.next_number)
        new = self._parse_check_number(candidate)
        if not current or not new:
            return True
        if (current[0], current[3]) != (new[0], new[3]):
            return True
        return new[1] > current[1]

    # -------------------------------------------------------------------------
    # Concurrencia
    # -------------------------------------------------------------------------

    def _lock_and_read_next_check_number(self):
        """Toma un lock exclusivo sobre la fila de la chequera y devuelve el valor en base.

        El lock se toma con un UPDATE que no cambia el valor, y no con
        ``SELECT ... FOR UPDATE``. En PostgreSQL el UPDATE genera una versión
        nueva de la fila aunque el valor sea el mismo; como Odoo trabaja en
        REPEATABLE READ, cualquier transacción que esté esperando esta fila
        falla por serialización cuando la nuestra confirma, y Odoo reintenta
        el request. En el reintento ya ve los cheques publicados, así que el
        control de duplicados los detecta. Con ``FOR UPDATE`` eso solo pasaría
        si además avanzamos el contador: publicar un número más bajo que el
        contador dejaría pasar un duplicado concurrente.

        Sin ``NOWAIT`` a propósito: el segundo pago espera en vez de fallar.

        Se invalida la cache para que las lecturas posteriores de
        ``next_number`` vean el valor real y no el que quedó en memoria antes
        de esperar el lock.

        Importante: quien controla números de cheque duplicados debe tomar
        este lock ANTES de ejecutar ese control, dentro de la misma
        transacción. Si el control se hace sin este lock, la protección por
        reintento de serialización descripta arriba no aplica y dos pagos
        concurrentes pueden no detectarse como duplicados entre sí.
        """
        self.ensure_one()
        self.flush_recordset(['next_number'])
        self.env.cr.execute(
            'UPDATE account_checkbook SET next_number = next_number WHERE id = %s RETURNING next_number',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        self.invalidate_recordset(['next_number'])
        return row[0] if row else False

    def _lock_checkbooks(self):
        """Bloquea varias chequeras de a una y en orden de id, para no generar deadlocks."""
        for checkbook in self.sorted('id'):
            checkbook._lock_and_read_next_check_number()

    def _increment_check_number(self, used_number=None):
        """Avanza el contador en base al número efectivamente emitido.

        Se usa ``sudo()`` porque la escritura sobre ``account.checkbook`` está
        reservada a ``account.group_account_manager`` y quien postea el pago
        puede ser un usuario de Facturación.
        """
        self.ensure_one()
        if not self.active:
            return
        # Serializa el avance del contador entre pagos publicados en paralelo.
        self._lock_and_read_next_check_number()
        candidate = self._calculate_next_number(used_number)
        if not candidate or candidate == self.next_number:
            return
        if not self._is_check_number_ahead(candidate):
            _logger.info(
                'Chequera %s: se ignora el retroceso de la secuencia de cheques '
                '(actual: %s, calculado: %s).',
                self.display_name, self.next_number, candidate,
            )
            return
        self.sudo().next_number = candidate
