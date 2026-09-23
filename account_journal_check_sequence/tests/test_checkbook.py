from psycopg2 import IntegrityError

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import CheckbookTestCommon


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
        """Bloquear varias chequeras hace flush e invalida la cache de cada una.

        Se verifica contra la base, no contra la cache del recordset: si
        ``_lock_checkbooks`` no bloqueara alguna chequera, el flush pendiente
        no llegaría a la base o la cache en memoria quedaría con un valor
        viejo, y las lecturas de abajo no lo detectarían.
        """
        other = self.checkbook.copy({'name': 'Otra', 'next_number': '00000050'})
        self.env.flush_all()
        other.next_number = '00000060'  # Cambio en memoria, sin flush.
        self.env.cr.execute(
            "UPDATE account_checkbook SET next_number = '00001020' WHERE id = %s",
            (self.checkbook.id,),
        )
        (self.checkbook | other)._lock_checkbooks()
        self.env.cr.execute(
            'SELECT next_number FROM account_checkbook WHERE id = %s',
            (other.id,),
        )
        self.assertEqual(
            self.env.cr.fetchone()[0], '00000060',
            'El lock debe hacer flush del valor pendiente antes de bloquear.',
        )
        self.assertEqual(
            self.checkbook.next_number, '00001020',
            'El lock debe invalidar la cache para leer el valor real en base.',
        )

    def test_archived_checkbook_does_not_advance(self):
        """Una chequera archivada no avanza al postear."""
        self.checkbook.active = False
        self.checkbook._increment_check_number('00001001')
        self.assertEqual(self.checkbook.next_number, '00001001')

    def test_padding_constraint(self):
        """La cantidad de dígitos está acotada."""
        with self.assertRaises(ValidationError):
            self.checkbook.padding = 99


@tagged('post_install', '-at_install')
class TestCheckbookSharing(CheckbookTestCommon):
    """Varios diarios, de una o varias compañías, sobre la misma chequera."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal_b = cls._create_bank_journal('Banco Sucursal B', 'BSUB', checkbook=cls.checkbook)
        cls.own_checks_line_b = cls._setup_own_checks_line(cls.journal_b, cls.outstanding_account)

    def test_shared_checkbook_continues_across_journals(self):
        """Lo que publica un diario lo ve el otro: sugiere el número siguiente."""
        payment_a = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        payment_a.action_post()
        self.assertEqual(payment_a.l10n_latam_new_check_ids.name, '00001001')

        payment_b = self._create_own_check_payment(
            [{'payment_date': self.check_date, 'amount': 20}],
            journal=self.journal_b, own_checks_line=self.own_checks_line_b,
        )
        self.assertEqual(payment_b.l10n_latam_new_check_ids.name, '00001002')

    def test_shared_journals_computed(self):
        """El diario informa qué otros diarios comparten su chequera."""
        self.assertEqual(self.bank_journal.checkbook_shared_journal_ids, self.journal_b)
        self.assertEqual(self.journal_b.checkbook_shared_journal_ids, self.bank_journal)

    def test_edit_next_number_from_journal_updates_checkbook(self):
        """Editar el número desde un diario cambia la chequera de todos."""
        self.journal_b.next_check_number = '00002000'
        self.assertEqual(self.checkbook.next_number, '00002000')
        self.assertEqual(self.bank_journal.next_check_number, '00002000')

    def test_enabled_follows_checkbook(self):
        """La numeración está activa si el diario tiene una chequera activa."""
        self.assertTrue(self.bank_journal.check_sequence_enabled)
        self.checkbook.active = False
        self.assertFalse(self.bank_journal.check_sequence_enabled)

    def test_archived_checkbook_disables_numbering(self):
        """Con la chequera archivada no se sugiere número ni avanza al publicar."""
        self.checkbook.active = False
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        self.assertFalse(payment.l10n_latam_new_check_ids.name)
        payment.l10n_latam_new_check_ids.name = '00005000'
        payment.action_post()
        self.assertEqual(self.checkbook.next_number, '00001001')

    def test_cannot_delete_checkbook_in_use(self):
        """Una chequera asignada a un diario no se puede borrar, solo archivar."""
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.checkbook.unlink()

    def test_checkbook_company_must_match_journal(self):
        """Una chequera de otra compañía no se puede asignar al diario."""
        company_2 = self.setup_other_company()['company']
        # sudo defensivo: que la regla multicompañía no dependa de las compañías activas.
        foreign_checkbook = self.env['account.checkbook'].sudo().create({
            'name': 'Chequera Compañía 2',
            'company_id': company_2.id,
        })
        with self.assertRaises(ValidationError):
            self.bank_journal.sudo().checkbook_id = foreign_checkbook

    def test_branch_journal_uses_parent_checkbook(self):
        """Un diario de una sucursal puede usar la chequera de la compañía madre."""
        branch = self._create_company(name='Sucursal Rama', parent_id=self.company_data['company'].id)
        self.checkbook.company_id = self.company_data['company']
        branch_journal = self._create_bank_journal('Banco Rama', 'BRAM', company=branch, checkbook=self.checkbook)
        self.assertEqual(branch_journal.checkbook_id, self.checkbook)

    def test_checkbook_company_change_checks_journals(self):
        """Cambiarle la compañía a una chequera en uso valida sus diarios."""
        company_2 = self.setup_other_company()['company']
        with self.assertRaises(ValidationError):
            self.checkbook.company_id = company_2


@tagged('post_install', '-at_install')
class TestCheckbookMultiCompany(CheckbookTestCommon):
    """Una chequera sin compañía compartida por diarios de dos compañías."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_second_company()
        cls.journal_c2 = cls.env['account.journal'].browse(cls.company_data_2['default_journal_bank'].id)
        cls.journal_c2.checkbook_id = cls.checkbook
        cls.own_checks_line_c2 = cls._setup_own_checks_line(cls.journal_c2, cls.outstanding_account_2)

    def test_counter_advances_from_both_companies(self):
        """Publicar desde cada compañía avanza el mismo contador."""
        payment_1 = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        payment_1.action_post()
        payment_2 = self._create_own_check_payment(
            [{'payment_date': self.check_date, 'amount': 20}],
            journal=self.journal_c2, own_checks_line=self.own_checks_line_c2,
        )
        self.assertEqual(payment_2.l10n_latam_new_check_ids.name, '00001002')
        payment_2.action_post()
        self.assertEqual(self.checkbook.next_number, '00001003')
