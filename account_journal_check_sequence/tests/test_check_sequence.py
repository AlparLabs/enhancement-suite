# account_journal_check_sequence/tests/test_check_sequence.py
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged


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

    def test_lock_reads_persisted_value(self):
        """El lock devuelve el valor en base y descarta la cache en memoria."""
        self.bank_journal.next_check_number = '00001007'
        self.assertEqual(self.bank_journal._lock_and_read_next_check_number(), '00001007')

    def test_increment_recalculates_after_lock(self):
        """Tras tomar el lock, el contador se evalúa sobre el valor real en base.

        Simula al segundo pago concurrente: el diario ya avanzó en base y la
        cache del recordset quedó vieja. El lock invalida esa cache, así que el
        retroceso se detecta y el contador no se pisa.
        """
        self.bank_journal.next_check_number = '00001001'
        self.bank_journal.flush_recordset(['next_check_number'])
        # Otro pago ya avanzo la secuencia por fuera de este recordset.
        self.env.cr.execute(
            "UPDATE account_journal SET next_check_number = '00001010' WHERE id = %s",
            (self.bank_journal.id,),
        )
        self.bank_journal._increment_check_number('00001001')
        self.assertEqual(self.bank_journal.next_check_number, '00001010')

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

    def test_form_new_line_does_not_repeat_number(self):
        """Agregar líneas en la pestaña Cheques no repite el mismo número.

        Reproduce el flujo de la interfaz: el valor por defecto de cada línea
        nueva sale del contador del diario, que no avanza hasta postear, así
        que sin encadenado las dos líneas nacerían con el mismo número.
        """
        with Form(self.env['account.payment'].with_context(default_payment_type='outbound')) as payment_form:
            payment_form.partner_id = self.partner_a
            payment_form.journal_id = self.bank_journal
            payment_form.payment_method_line_id = self.own_checks_line
            with payment_form.l10n_latam_new_check_ids.new() as check_1:
                check_1.payment_date = self.check_date
                check_1.amount = 10
            with payment_form.l10n_latam_new_check_ids.new() as check_2:
                check_2.payment_date = self.check_date
                check_2.amount = 20
        payment = payment_form.save()
        self.assertEqual(
            payment.l10n_latam_new_check_ids.mapped('name'),
            ['00001001', '00001002'],
        )

    def test_suggestion_renumbers_autofilled_duplicate(self):
        """Un número puesto por el módulo que quedó duplicado se re-encadena."""
        payment = self._create_own_check_payment([
            {'name': '00001001', 'autofilled_check_number': '00001001',
             'payment_date': self.check_date, 'amount': 10},
            {'name': '00001001', 'autofilled_check_number': '00001001',
             'payment_date': self.check_date, 'amount': 20},
        ])
        payment._apply_check_sequence_suggestion()
        self.assertEqual(
            payment.l10n_latam_new_check_ids.mapped('name'),
            ['00001001', '00001002'],
        )

    def test_suggestion_respects_user_typed_duplicate(self):
        """Un número tipeado por el usuario no se reescribe, ni aunque repita.

        Sin `autofilled_check_number` el módulo no puede saber que ese valor lo
        puso él, así que lo trata como carga manual. Si el usuario se equivocó,
        el índice único de l10n_latam.check se lo va a marcar al publicar: es
        preferible eso a cambiarle en silencio un número que escribió a mano.
        """
        payment = self._create_own_check_payment([
            {'name': '00001001', 'payment_date': self.check_date, 'amount': 10},
            {'name': '00001001', 'payment_date': self.check_date, 'amount': 20},
        ])
        payment._apply_check_sequence_suggestion()
        self.assertEqual(
            payment.l10n_latam_new_check_ids.mapped('name'),
            ['00001001', '00001001'],
        )

    def test_suggestion_recalculates_edited_autofilled_line(self):
        """Si el usuario edita un número autocompletado, pasa a respetarse."""
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
            {'payment_date': self.check_date, 'amount': 20},
        ])
        first, second = payment.l10n_latam_new_check_ids
        first.name = '00001050'
        payment._apply_check_sequence_suggestion()
        self.assertEqual(first.name, '00001050', 'El valor editado a mano se respeta.')
        self.assertEqual(
            second.name, '00001051',
            'La línea autocompletada encadena desde el número editado.',
        )

    def test_create_marks_autofilled_number(self):
        """El número asignado por el módulo queda marcado como autocompletado."""
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        check = payment.l10n_latam_new_check_ids
        self.assertEqual(check.name, '00001001')
        self.assertEqual(check.autofilled_check_number, '00001001')

    def test_create_does_not_mark_manual_number(self):
        """Un número pasado explícitamente no se marca como autocompletado."""
        payment = self._create_own_check_payment([
            {'name': '00001020', 'payment_date': self.check_date, 'amount': 10},
        ])
        self.assertFalse(payment.l10n_latam_new_check_ids.autofilled_check_number)

    def test_next_number_computed_from_loaded_lines(self):
        """El próximo número sugerido contempla las líneas ya cargadas."""
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
            {'payment_date': self.check_date, 'amount': 20},
        ])
        self.assertEqual(payment.check_sequence_next_number, '00001003')

    def test_next_number_empty_out_of_scope(self):
        """Fuera del alcance del módulo no se sugiere ningún número."""
        self.bank_journal.check_sequence_enabled = False
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        self.assertFalse(payment.check_sequence_next_number)

    def test_suggestion_keeps_distinct_manual_numbers(self):
        """Números distintos cargados a mano no se tocan."""
        payment = self._create_own_check_payment([
            {'name': '00001010', 'payment_date': self.check_date, 'amount': 10},
            {'name': '00001020', 'payment_date': self.check_date, 'amount': 20},
        ])
        payment._apply_check_sequence_suggestion()
        self.assertEqual(
            payment.l10n_latam_new_check_ids.mapped('name'),
            ['00001010', '00001020'],
        )

    def test_default_get_chains_from_existing_lines(self):
        """El valor por defecto encadena desde los cheques ya cargados en el pago."""
        payment = self._create_own_check_payment([
            {'payment_date': self.check_date, 'amount': 10},
        ])
        defaults = self.env['l10n_latam.check'].with_context(
            default_payment_id=payment.id,
        ).default_get(['name'])
        self.assertEqual(defaults.get('name'), '00001002')

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

    def test_default_get_uses_context_next_number(self):
        """El próximo número publicado por el padre en el contexto tiene prioridad.

        Es el camino que usa la interfaz: contempla las líneas cargadas en el
        cliente que todavía no se guardaron y que `default_get` no puede ver.
        """
        defaults = self.env['l10n_latam.check'].with_context(
            check_sequence_next_number='00001099',
        ).default_get(['name'])
        self.assertEqual(defaults.get('name'), '00001099')
        self.assertEqual(defaults.get('autofilled_check_number'), '00001099')

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
