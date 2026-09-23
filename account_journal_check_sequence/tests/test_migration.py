import importlib.util

from odoo.tests import tagged
from odoo.tools.misc import file_path

from .common import CheckbookTestCommon


def _load_migrate():
    """Carga ``migrate`` del script (el nombre de carpeta no es importable)."""
    path = file_path('account_journal_check_sequence/migrations/19.0.1.3.0/post-migrate.py')
    spec = importlib.util.spec_from_file_location('check_sequence_migrate_19_0_1_3_0', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged('post_install', '-at_install')
class TestMigration(CheckbookTestCommon):

    def _add_legacy_columns(self):
        """Recrea las columnas que la versión 19.0.1.2.0 dejaba en account_journal.

        En una base actualizada existen (Odoo no borra columnas); en la base de
        tests, instalada de cero, no. El DDL se deshace con la transacción del test.
        """
        self.env.cr.execute("""
            ALTER TABLE account_journal
                ADD COLUMN IF NOT EXISTS check_sequence_enabled boolean,
                ADD COLUMN IF NOT EXISTS next_check_number varchar,
                ADD COLUMN IF NOT EXISTS check_number_padding integer
        """)

    def test_migration_creates_checkbook_and_backfills_checks(self):
        # Diario que en 19.0.1.2.0 numeraba por su cuenta y ya emitió un cheque.
        legacy_journal = self._create_bank_journal('Banco Legado', 'BLEG')
        legacy_line = self._setup_own_checks_line(legacy_journal, self.outstanding_account)
        legacy_payment = self._create_own_check_payment(
            [{'name': '00000700', 'payment_date': self.check_date, 'amount': 10}],
            journal=legacy_journal, own_checks_line=legacy_line,
        )
        legacy_payment.action_post()
        self.env.flush_all()
        self._add_legacy_columns()
        self.env.cr.execute("""
            UPDATE account_journal
               SET check_sequence_enabled = TRUE,
                   next_check_number = ' 00000701 ',
                   check_number_padding = 99
             WHERE id = %s
        """, (legacy_journal.id,))

        migrate = _load_migrate()
        migrate(self.env.cr, '19.0.1.2.0')
        self.env.invalidate_all()

        checkbook = legacy_journal.checkbook_id
        self.assertTrue(checkbook)
        self.assertEqual(checkbook.name, 'Banco Legado')
        self.assertEqual(checkbook.next_number, '00000701')
        self.assertEqual(checkbook.padding, 8, 'Un padding fuera de rango vuelve al default.')
        self.assertEqual(checkbook.company_id, legacy_journal.company_id)
        self.assertEqual(legacy_payment.l10n_latam_new_check_ids.checkbook_id, checkbook)

        checkbook_count = self.env['account.checkbook'].with_context(active_test=False).search_count([])
        migrate(self.env.cr, '19.0.1.2.0')
        self.assertEqual(
            self.env['account.checkbook'].with_context(active_test=False).search_count([]),
            checkbook_count,
            'La migración es idempotente.',
        )

    def test_migration_skips_without_legacy_columns(self):
        """Sin las columnas viejas de account_journal no hace nada."""
        self.env.cr.execute("""
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'account_journal'
               AND column_name = 'check_sequence_enabled'
        """)
        if self.env.cr.fetchone():
            self.skipTest('La base de tests tiene las columnas viejas (base actualizada).')
        checkbook_count = self.env['account.checkbook'].with_context(active_test=False).search_count([])
        _load_migrate()(self.env.cr, '19.0.1.2.0')
        self.assertEqual(
            self.env['account.checkbook'].with_context(active_test=False).search_count([]),
            checkbook_count,
        )

    def test_migration_skips_fresh_install(self):
        """Sin versión previa no hace nada."""
        checkbook_count = self.env['account.checkbook'].search_count([])
        _load_migrate()(self.env.cr, None)
        self.assertEqual(self.env['account.checkbook'].search_count([]), checkbook_count)
