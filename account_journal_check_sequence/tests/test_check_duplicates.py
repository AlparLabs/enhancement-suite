from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import CheckbookTestCommon


@tagged('post_install', '-at_install')
class TestCheckDuplicates(CheckbookTestCommon):
    """Un número ya emitido en la chequera no se puede volver a usar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal_b = cls._create_bank_journal('Banco Sucursal B', 'BSUB', checkbook=cls.checkbook)
        cls.own_checks_line_b = cls._setup_own_checks_line(cls.journal_b, cls.outstanding_account)

    def _post_check(self, number, journal=None, own_checks_line=None):
        payment = self._create_own_check_payment(
            [{'name': number, 'payment_date': self.check_date, 'amount': 10}],
            journal=journal, own_checks_line=own_checks_line,
        )
        payment.action_post()
        return payment

    def _draft_check_in_b(self, number):
        return self._create_own_check_payment(
            [{'name': number, 'payment_date': self.check_date, 'amount': 10}],
            journal=self.journal_b, own_checks_line=self.own_checks_line_b,
        )

    def test_post_sets_checkbook_on_checks(self):
        """Al publicar, cada cheque queda asociado a la chequera que lo emitió."""
        payment = self._post_check('00001050')
        self.assertEqual(payment.l10n_latam_new_check_ids.checkbook_id, self.checkbook)

    def test_duplicate_across_journals_warns_and_blocks(self):
        """El mismo número desde otro diario de la chequera avisa y bloquea."""
        self._post_check('00001050')
        payment_b = self._draft_check_in_b('00001050')
        self.assertIn('00001050', payment_b.l10n_latam_check_warning_msg or '')
        self.assertIn('Chequera Test', payment_b.l10n_latam_check_warning_msg)
        with self.assertRaises(ValidationError):
            payment_b.action_post()

    def test_duplicate_within_payment_blocks(self):
        """El mismo número dos veces en un pago también bloquea."""
        payment = self._create_own_check_payment([
            {'name': '00001050', 'payment_date': self.check_date, 'amount': 10},
            {'name': '00001050', 'payment_date': self.check_date, 'amount': 20},
        ])
        self.assertIn('más de una vez', payment.l10n_latam_check_warning_msg or '')
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_canceled_payment_does_not_block(self):
        """Un número de un pago cancelado queda libre."""
        payment = self._post_check('00001050')
        payment.action_cancel()
        payment_b = self._draft_check_in_b('00001050')
        payment_b.action_post()
        # Según la cuenta de pagos pendientes, el pago publicado queda
        # 'in_process' o 'paid': lo que importa es que se haya publicado.
        self.assertNotIn(payment_b.state, ('draft', 'canceled'))

    def test_draft_payment_does_not_block(self):
        """Un número cargado en un borrador todavía no está emitido."""
        self._create_own_check_payment([
            {'name': '00001050', 'payment_date': self.check_date, 'amount': 10},
        ])
        payment_b = self._draft_check_in_b('00001050')
        self.assertFalse(payment_b.l10n_latam_check_warning_msg)
        payment_b.action_post()

    def test_voided_check_blocks(self):
        """Un cheque anulado igual ocupó su número."""
        payment = self._post_check('00001050')
        payment.l10n_latam_new_check_ids.action_void()
        with self.assertRaises(ValidationError):
            self._draft_check_in_b('00001050').action_post()

    def test_other_checkbook_does_not_block(self):
        """El mismo número en otra chequera no es un duplicado."""
        other = self.env['account.checkbook'].create({'name': 'Otra', 'next_number': '00000001'})
        journal_c = self._create_bank_journal('Banco C', 'BNCC', checkbook=other)
        line_c = self._setup_own_checks_line(journal_c, self.outstanding_account)
        self._post_check('00001050')
        self._post_check('00001050', journal=journal_c, own_checks_line=line_c)

    def test_previous_checkbook_of_journal_does_not_block(self):
        """Los cheques emitidos con la chequera anterior de un diario no cuentan."""
        other = self.env['account.checkbook'].create({'name': 'Anterior', 'next_number': '00000001'})
        self.journal_b.checkbook_id = other
        self._post_check('00001050', journal=self.journal_b, own_checks_line=self.own_checks_line_b)
        self.journal_b.checkbook_id = self.checkbook
        self._post_check('00001050')

    def test_journal_without_checkbook_skips_control(self):
        """Sin chequera, el módulo no controla (queda solo el índice nativo)."""
        journal_c = self._create_bank_journal('Banco C', 'BNCC')
        line_c = self._setup_own_checks_line(journal_c, self.outstanding_account)
        self._post_check('00001050')
        self._post_check('00001050', journal=journal_c, own_checks_line=line_c)
