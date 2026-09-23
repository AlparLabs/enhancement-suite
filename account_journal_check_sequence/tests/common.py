from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class CheckbookTestCommon(AccountTestInvoicingCommon):
    """Diario de banco con método Cheque Propio y una chequera asignada."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.checkbook = cls.env['account.checkbook'].create({
            'name': 'Chequera Test',
            'next_number': '00001001',
            'padding': 8,
        })
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.bank_journal.checkbook_id = cls.checkbook
        cls.outstanding_account = cls.outbound_payment_method_line.payment_account_id
        cls.own_checks_line = cls._setup_own_checks_line(cls.bank_journal, cls.outstanding_account)
        cls.check_date = fields.Date.add(fields.Date.today(), months=1)

    @classmethod
    def _setup_own_checks_line(cls, journal, outstanding_account):
        """Agrega el método Cheque Propio al diario y devuelve su línea."""
        journal.outbound_payment_method_line_ids = [
            Command.create({
                'payment_method_id': cls.env.ref('l10n_latam_check.account_payment_method_own_checks').id,
                'name': 'Own Checks',
            }),
        ]
        line = journal.outbound_payment_method_line_ids.filtered(lambda method: method.code == 'own_checks')
        line.payment_account_id = outstanding_account
        return line

    @classmethod
    def _setup_second_company(cls):
        """Crea una segunda compañía y la deja activa junto con la primera.

        Sin ``allowed_company_ids`` el entorno ya toma todas las compañías del
        usuario; el cambio de entorno solo deja las dos activas de forma
        explícita, para que los tests no dependan de ese fallback. Los
        registros de clase se vuelven a leer con el entorno nuevo.
        """
        cls.company_data_2 = cls.setup_other_company()
        cls.company_2 = cls.company_data_2['company']
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=(cls.company_data['company'] | cls.company_2).ids,
        ))
        cls.checkbook = cls.env['account.checkbook'].browse(cls.checkbook.id)
        cls.bank_journal = cls.env['account.journal'].browse(cls.bank_journal.id)
        cls.own_checks_line = cls.env['account.payment.method.line'].browse(cls.own_checks_line.id)
        cls.outstanding_account_2 = cls.outstanding_account.copy({
            'company_ids': [Command.set(cls.company_2.ids)],
        })

    @classmethod
    def _create_bank_journal(cls, name, code, company=None, checkbook=None):
        company = company or cls.company_data['company']
        return cls.env['account.journal'].with_company(company).create({
            'name': name,
            'code': code,
            'type': 'bank',
            'company_id': company.id,
            'checkbook_id': checkbook.id if checkbook else False,
        })

    def _create_own_check_payment(self, checks_vals, journal=None, own_checks_line=None):
        journal = journal or self.bank_journal
        own_checks_line = own_checks_line or self.own_checks_line
        return self.env['account.payment'].with_company(journal.company_id).create({
            'payment_type': 'outbound',
            'partner_id': self.partner_a.id,
            'journal_id': journal.id,
            'payment_method_line_id': own_checks_line.id,
            'l10n_latam_new_check_ids': [Command.create(vals) for vals in checks_vals],
        })
