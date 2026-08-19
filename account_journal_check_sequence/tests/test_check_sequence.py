# account_journal_check_sequence/tests/test_check_sequence.py
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCheckSequence(TransactionCase):

    def setUp(self):
        super().setUp()
        self.bank_journal = self.env['account.journal'].create({
            'name': 'Banco Galicia Test',
            'type': 'bank',
            'code': 'BGT',
            'check_sequence_enabled': True,
            'next_check_number': '00001001',
            'check_number_padding': 8,
        })

    def test_01_journal_check_number_format(self):
        """Verifica que el número de cheque se formatee correctamente con padding."""
        formatted = self.bank_journal._get_next_check_number_formatted()
        self.assertEqual(formatted, '00001001')

    def test_02_journal_check_increment(self):
        """Verifica el incremento automático básico del diario."""
        self.bank_journal._increment_check_number('00001001')
        self.assertEqual(self.bank_journal.next_check_number, '00001002')

    def test_03_journal_check_manual_skip(self):
        """Verifica que si se utiliza un número manual superior, el contador avance a partir de él."""
        self.bank_journal._increment_check_number('00001050')
        self.assertEqual(self.bank_journal.next_check_number, '00001051')

    def test_04_journal_check_with_prefix(self):
        """Verifica incremento cuando se usa un prefijo (ej. Echeqs 'E-00000100')."""
        self.bank_journal.next_check_number = 'E-00000100'
        self.bank_journal._increment_check_number('E-00000100')
        self.assertEqual(self.bank_journal.next_check_number, 'E-00000101')
