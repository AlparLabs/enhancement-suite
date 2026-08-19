import re
from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    check_sequence_enabled = fields.Boolean(
        string='Auto-numerar Cheques Propios',
        default=True,
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
        default=8,
        help='Cantidad de dígitos con ceros a la izquierda para formatear el número de cheque (ej. 8 para 00000001).'
    )

    def _get_next_check_number_formatted(self):
        """Devuelve el próximo número formateado según el padding configurado."""
        self.ensure_one()
        current_num = (self.next_check_number or '1').strip()
        match = re.match(r'^(.*?)(\d+)(\D*)$', current_num)
        if match:
            prefix, digits_str, suffix = match.groups()
            padding = max(self.check_number_padding or 8, len(digits_str))
            val = int(digits_str)
            return f"{prefix}{str(val).zfill(padding)}{suffix}"
        return current_num

    def _increment_check_number(self, used_number=None):
        """
        Incrementa la secuencia del diario en base al número efectivamente utilizado
        o en base al valor actual si no se proporciona uno.
        """
        self.ensure_one()
        if not self.check_sequence_enabled:
            return

        ref_str = str(used_number).strip() if used_number else str(self.next_check_number or '0').strip()
        match = re.match(r'^(.*?)(\d+)(\D*)$', ref_str)
        if match:
            try:
                prefix, digits_str, suffix = match.groups()
                used_val = int(digits_str)
                next_val = used_val + 1
                padding = max(self.check_number_padding or 8, len(digits_str))
                self.next_check_number = f"{prefix}{str(next_val).zfill(padding)}{suffix}"
            except (ValueError, IndexError):
                pass
