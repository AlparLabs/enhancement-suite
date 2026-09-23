from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestCheckbookCounter(AccountTestInvoicingCommon):
    """Lógica de numeración de la chequera, sin pagos de por medio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.checkbook = cls.env['account.checkbook'].create({
            'name': 'Chequera Test',
            'next_number': '00001001',
            'padding': 8,
        })

    def test_format(self):
        """El próximo número se formatea con el padding configurado."""
        self.assertEqual(self.checkbook._get_next_check_number_formatted(), '00001001')

    def test_increment(self):
        """El contador avanza uno respecto del número emitido."""
        self.checkbook._increment_check_number('00001001')
        self.assertEqual(self.checkbook.next_number, '00001002')

    def test_manual_skip(self):
        """Si el usuario saltea números, el contador arranca desde el usado."""
        self.checkbook._increment_check_number('00001050')
        self.assertEqual(self.checkbook.next_number, '00001051')

    def test_never_goes_backwards(self):
        """Postear un cheque anterior no debe hacer retroceder el contador."""
        self.checkbook._increment_check_number('00000500')
        self.assertEqual(
            self.checkbook.next_number, '00001001',
            'El contador no puede retroceder: llevaría a sugerir números ya emitidos.',
        )

    def test_with_prefix(self):
        """Se preserva el prefijo de la serie (ej. Echeqs 'E-00000100')."""
        self.checkbook.next_number = 'E-00000100'
        self.checkbook._increment_check_number('E-00000100')
        self.assertEqual(self.checkbook.next_number, 'E-00000101')

    def test_series_change_allowed(self):
        """Un cambio de serie (otro prefijo) sí puede reposicionar el contador."""
        self.checkbook._increment_check_number('E-00000100')
        self.assertEqual(self.checkbook.next_number, 'E-00000101')

    def test_peek_does_not_persist(self):
        """Consultar los próximos números no modifica la chequera."""
        self.assertEqual(self.checkbook._peek_check_numbers(3), ['00001001', '00001002', '00001003'])
        self.assertEqual(self.checkbook.next_number, '00001001')

    def test_highest_check_number(self):
        """El número más alto se resuelve por valor numérico, no por posición."""
        self.assertEqual(
            self.checkbook._get_highest_check_number(['00001003', '00001010', '00001005']),
            '00001010',
        )

    def test_lock_reads_persisted_value(self):
        """El lock devuelve el valor en base y descarta la cache en memoria."""
        self.checkbook.next_number = '00001007'
        self.assertEqual(self.checkbook._lock_and_read_next_check_number(), '00001007')

    def test_increment_recalculates_after_lock(self):
        """Tras tomar el lock, el contador se evalúa sobre el valor real en base.

        Simula al segundo pago concurrente: la chequera ya avanzó en base y la
        cache del recordset quedó vieja. El lock invalida esa cache, así que el
        retroceso se detecta y el contador no se pisa.
        """
        self.checkbook.flush_recordset(['next_number'])
        self.env.cr.execute(
            "UPDATE account_checkbook SET next_number = '00001010' WHERE id = %s",
            (self.checkbook.id,),
        )
        self.checkbook._increment_check_number('00001001')
        self.assertEqual(self.checkbook.next_number, '00001010')

    def test_lock_checkbooks_locks_every_record(self):
        """Bloquear varias chequeras deja a cada una con su valor en base."""
        other = self.checkbook.copy({'name': 'Otra', 'next_number': '00000050'})
        (self.checkbook | other)._lock_checkbooks()
        self.assertEqual(other.next_number, '00000050')
        self.assertEqual(self.checkbook.next_number, '00001001')

    def test_archived_checkbook_does_not_advance(self):
        """Una chequera archivada no avanza al postear."""
        self.checkbook.active = False
        self.checkbook._increment_check_number('00001001')
        self.assertEqual(self.checkbook.next_number, '00001001')

    def test_padding_constraint(self):
        """La cantidad de dígitos está acotada."""
        with self.assertRaises(ValidationError):
            self.checkbook.padding = 99
