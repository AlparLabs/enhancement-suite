from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CheckbookTestCommon


@tagged('post_install', '-at_install')
class TestCheckbookMerge(CheckbookTestCommon):
    """Unificar chequeras de sucursales que comparten la chequera física."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_second_company()
        company_2 = cls.company_2

        # Sucursal B: misma compañía, chequera propia creada por la migración.
        cls.checkbook_b = cls.env['account.checkbook'].create({
            'name': 'Chequera B', 'next_number': '00001040',
            'company_id': cls.company_data['company'].id,
        })
        cls.journal_b = cls._create_bank_journal('Banco Sucursal B', 'BSUB', checkbook=cls.checkbook_b)
        cls.own_checks_line_b = cls._setup_own_checks_line(cls.journal_b, cls.outstanding_account)

        # Sucursal C: otra compañía.
        cls.checkbook_c = cls.env['account.checkbook'].create({
            'name': 'Chequera C', 'next_number': '00001020', 'company_id': company_2.id,
        })
        cls.journal_c = cls.env['account.journal'].browse(cls.company_data_2['default_journal_bank'].id)
        cls.journal_c.checkbook_id = cls.checkbook_c

    def _merge_wizard(self, checkbooks, **vals):
        return self.env['account.checkbook.merge'].with_context(
            active_model='account.checkbook', active_ids=checkbooks.ids,
        ).create(vals)

    def test_defaults(self):
        """Propone el número más alto y deja la compañía vacía si hay varias."""
        wizard = self._merge_wizard(self.checkbook | self.checkbook_b | self.checkbook_c)
        self.assertEqual(wizard.checkbook_ids, self.checkbook | self.checkbook_b | self.checkbook_c)
        self.assertEqual(wizard.next_number, '00001040')
        self.assertFalse(wizard.company_id)
        self.assertIn(wizard.target_checkbook_id, wizard.checkbook_ids)

    def test_merge_moves_journals_and_archives_sources(self):
        """Todos los diarios quedan en la destino, sin compañía; el resto se archiva."""
        wizard = self._merge_wizard(
            self.checkbook | self.checkbook_b | self.checkbook_c,
            target_checkbook_id=self.checkbook.id,
        )
        wizard.action_merge()
        self.assertEqual(self.journal_b.checkbook_id, self.checkbook)
        self.assertEqual(self.journal_c.checkbook_id, self.checkbook)
        self.assertFalse(self.checkbook.company_id)
        self.assertEqual(self.checkbook.next_number, '00001040')
        self.assertFalse(self.checkbook_b.active)
        self.assertFalse(self.checkbook_c.active)

    def test_merge_moves_issued_checks(self):
        """Los cheques emitidos pasan a la destino y el control de duplicados los ve."""
        payment_b = self._create_own_check_payment(
            [{'name': '00001040', 'payment_date': self.check_date, 'amount': 10}],
            journal=self.journal_b, own_checks_line=self.own_checks_line_b,
        )
        payment_b.action_post()
        self._merge_wizard(
            self.checkbook | self.checkbook_b, target_checkbook_id=self.checkbook.id,
        ).action_merge()
        self.assertEqual(payment_b.l10n_latam_new_check_ids.checkbook_id, self.checkbook)
        payment_a = self._create_own_check_payment([
            {'name': '00001040', 'payment_date': self.check_date, 'amount': 10},
        ])
        with self.assertRaises(ValidationError):
            payment_a.action_post()

    def test_edited_next_number_is_respected(self):
        """El próximo número elegido por el usuario se respeta aunque sea menor."""
        self._merge_wizard(
            self.checkbook | self.checkbook_b,
            target_checkbook_id=self.checkbook.id,
            next_number='00000900',
        ).action_merge()
        self.assertEqual(self.checkbook.next_number, '00000900')

    def test_same_company_keeps_company(self):
        """Si todos los diarios son de la misma compañía, la destino la conserva."""
        wizard = self._merge_wizard(self.checkbook | self.checkbook_b, target_checkbook_id=self.checkbook_b.id)
        self.assertEqual(wizard.company_id, self.company_data['company'])
        wizard.action_merge()
        self.assertEqual(self.checkbook_b.company_id, self.company_data['company'])
        self.assertEqual(self.bank_journal.checkbook_id, self.checkbook_b)

    def test_branch_company_keeps_parent(self):
        """Diarios de una compañía y de su sucursal: la destino queda en la compañía madre."""
        company = self.company_data['company']
        branch = self._create_company(name='Sucursal Rama', parent_id=company.id)
        checkbook_branch = self.env['account.checkbook'].create({
            'name': 'Chequera Rama', 'next_number': '00000500', 'company_id': branch.id,
        })
        journal_branch = self._create_bank_journal(
            'Banco Rama', 'BRAM', company=branch, checkbook=checkbook_branch,
        )
        wizard = self._merge_wizard(
            self.checkbook_b | checkbook_branch, target_checkbook_id=self.checkbook_b.id,
        )
        self.assertEqual(wizard.company_id, company)
        wizard.action_merge()
        self.assertEqual(self.checkbook_b.company_id, company)
        self.assertEqual(journal_branch.checkbook_id, self.checkbook_b)

    def test_duplicate_warning_does_not_block(self):
        """Los números ya repetidos entre las chequeras se informan pero no impiden unificar."""
        for journal, line in ((self.bank_journal, self.own_checks_line), (self.journal_b, self.own_checks_line_b)):
            self._create_own_check_payment(
                [{'name': '00000777', 'payment_date': self.check_date, 'amount': 10}],
                journal=journal, own_checks_line=line,
            ).action_post()
        wizard = self._merge_wizard(self.checkbook | self.checkbook_b, target_checkbook_id=self.checkbook.id)
        self.assertIn('00000777', wizard.duplicate_warning or '')
        wizard.action_merge()
        self.assertEqual(self.journal_b.checkbook_id, self.checkbook)

    def test_no_duplicate_warning_without_repeats(self):
        wizard = self._merge_wizard(self.checkbook | self.checkbook_b, target_checkbook_id=self.checkbook.id)
        self.assertFalse(wizard.duplicate_warning)

    def test_requires_two_checkbooks(self):
        with self.assertRaises(UserError):
            self._merge_wizard(self.checkbook, target_checkbook_id=self.checkbook.id).action_merge()

    def test_target_must_be_selected(self):
        with self.assertRaises(UserError):
            self._merge_wizard(
                self.checkbook | self.checkbook_b, target_checkbook_id=self.checkbook_c.id,
            ).action_merge()
