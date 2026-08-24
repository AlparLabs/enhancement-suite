# account_journal_check_sequence/tests/test_check_sequence.py
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestCheckSequence(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.bank_journal.write({
            'check_sequence_enabled': True,
            'next_check_number': '00001001',
            'check_number_padding': 8,
        })
        cls.bank_journal.outbound_payment_method_line_ids = [
            Command.create({
                'payment_method_id': cls.env.ref('l10n_latam_check.account_payment_method_own_checks').id,
                'name': 'Own Checks',
            }),
        ]
        cls.own_checks_line = cls.bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.code == 'own_checks'
        )
        cls.own_checks_line.payment_account_id = cls.outbound_payment_method_line.payment_account_id
        cls.check_date = fields.Date.add(fields.Date.today(), months=1)

    def _create_own_check_payment(self, checks_vals):
        return self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_id': self.partner_a.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.own_checks_line.id,
            'l10n_latam_new_check_ids': [Command.create(vals) for vals in checks_vals],
        })

    # -------------------------------------------------------------------------
    # Formateo y cálculo
    # -------------------------------------------------------------------------

    def test_journal_check_number_format(self):
        """El próximo número se formatea con el padding configurado."""
        self.assertEqual(self.bank_journal._get_next_check_number_formatted(), '00001001')

    def test_journal_check_increment(self):
        """El contador avanza uno respecto del número emitido."""
        self.bank_journal._increment_check_number('00001001')
        self.assertEqual(self.bank_journal.next_check_number, '00001002')

    def test_journal_check_manual_skip(self):
        """Si el usuario saltea números, el contador arranca desde el usado."""
        self.bank_journal._increment_check_number('00001050')
        self.assertEqual(self.bank_journal.next_check_number, '00001051')

    def test_journal_check_never_goes_backwards(self):
        """Postear un cheque anterior no debe hacer retroceder el contador."""
        self.bank_journal._increment_check_number('00000500')
        self.assertEqual(
            self.bank_journal.next_check_number, '00001001',
            'El contador no puede retroceder: llevaría a sugerir números ya emitidos.',
        )

    def test_journal_check_with_prefix(self):
        """Se preserva el prefijo de la serie (ej. Echeqs 'E-00000100')."""
        self.bank_journal.next_check_number = 'E-00000100'
        self.bank_journal._increment_check_number('E-00000100')
        self.assertEqual(self.bank_journal.next_check_number, 'E-00000101')

    def test_journal_check_series_change_allowed(self):
        """Un cambio de serie (otro prefijo) sí puede reposicionar el contador."""
        self.bank_journal._increment_check_number('E-00000100')
        self.assertEqual(self.bank_journal.next_check_number, 'E-00000101')

    def test_peek_check_numbers_does_not_persist(self):
        """Consultar los próximos números no modifica el diario."""
        numbers = self.bank_journal._peek_check_numbers(3)
        self.assertEqual(numbers, ['00001001', '00001002', '00001003'])
        self.assertEqual(self.bank_journal.next_check_number, '00001001')

    def test_highest_check_number(self):
        """El número más alto se resuelve por valor numérico, no por posición."""
        self.assertEqual(
            self.bank_journal._get_highest_check_number(['00001003', '00001010', '00001005']),
            '00001010',
        )

    def test_padding_constraint(self):
        """La cantidad de dígitos está acotada."""
        with self.assertRaises(ValidationError):
            self.bank_journal.check_number_padding = 99

    # -------------------------------------------------------------------------
    # Creación de cheques
    # -------------------------------------------------------------------------

    def test_batch_create_chains_numbers(self):
        """Crear varios cheques en un solo lote no repite el número."""
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
            {'payment_date': self.check_date, 'amount': 20},
            {'payment_date': self.check_date, 'amount': 30},
        ])
        self.assertEqual(
            payment.l10n_latam_new_check_ids.mapped('name'),
            ['00001001', '00001002', '00001003'],
        )

    def test_create_respects_manual_number(self):
        """Un número cargado a mano se respeta y encadena a partir de él."""
        payment = self._create_own_check_payment([
            {'name': '00001020', 'payment_date': self.check_date, 'amount': 10},
            {'payment_date': self.check_date, 'amount': 20},
        ])
        self.assertEqual(
            payment.l10n_latam_new_check_ids.mapped('name'),
            ['00001020', '00001021'],
        )

    def test_create_on_disabled_journal(self):
        """Con la auto-numeración apagada el módulo no interviene."""
        self.bank_journal.check_sequence_enabled = False
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        self.assertFalse(payment.l10n_latam_new_check_ids.name)

    def test_other_payment_method_is_out_of_scope(self):
        """Solo se numeran los cheques propios LATAM (`own_checks`)."""
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_id': self.partner_a.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.outbound_payment_method_line.id,
            'amount': 100,
        })
        self.assertFalse(payment._is_own_check_payment())
        self.assertFalse(payment._check_sequence_journal())
        payment.action_post()
        self.assertEqual(self.bank_journal.next_check_number, '00001001')

    def test_default_get_ignores_foreign_active_id(self):
        """Un active_id de otro modelo no debe usarse para resolver el pago."""
        defaults = self.env['l10n_latam.check'].with_context(
            active_model='res.partner',
            active_id=self.partner_a.id,
        ).default_get(['name'])
        self.assertFalse(defaults.get('name'))

    # -------------------------------------------------------------------------
    # Publicación del pago
    # -------------------------------------------------------------------------

    def test_action_post_advances_to_highest_number(self):
        """Al publicar, el contador avanza a partir del número más alto emitido."""
        payment = self._create_own_check_payment([
            {'name': '00001001', 'payment_date': self.check_date, 'amount': 10},
            {'name': '00001003', 'payment_date': self.check_date, 'amount': 20},
            {'name': '00001002', 'payment_date': self.check_date, 'amount': 30},
        ])
        payment.action_post()
        self.assertEqual(self.bank_journal.next_check_number, '00001004')

    def test_action_post_on_disabled_journal(self):
        """Con la auto-numeración apagada el contador no se toca al publicar."""
        self.bank_journal.check_sequence_enabled = False
        payment = self._create_own_check_payment([
            {'name': '00002000', 'payment_date': self.check_date, 'amount': 10},
        ])
        payment.action_post()
        self.assertEqual(self.bank_journal.next_check_number, '00001001')
