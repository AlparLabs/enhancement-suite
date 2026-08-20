# account_journal_check_sequence/tests/test_check_sequence.py
from odoo.exceptions import ValidationError
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

    def _new_check(self, name=False, autofilled=False):
        """Cheque en memoria (sin pago) para probar la asignación de números."""
        return self.env['l10n_latam.check'].new({
            'name': name,
            'autofilled_check_number': autofilled,
        })

    # ------------------------------------------------------------------
    # Formateo e incremento
    # ------------------------------------------------------------------
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

    def test_05_increment_ignored_when_disabled(self):
        """Si la chequera está desactivada el contador no se toca."""
        self.bank_journal.check_sequence_enabled = False
        self.bank_journal._increment_check_number('00002000')
        self.assertEqual(self.bank_journal.next_check_number, '00001001')

    # ------------------------------------------------------------------
    # La secuencia nunca retrocede
    # ------------------------------------------------------------------
    def test_10_increment_never_goes_backwards(self):
        """Reemitir un cheque viejo no debe hacer retroceder la chequera."""
        self.bank_journal._increment_check_number('00001050')
        self.assertEqual(self.bank_journal.next_check_number, '00001051')
        # El usuario reemite el cheque 00001000, muy anterior al contador actual.
        self.bank_journal._increment_check_number('00001000')
        self.assertEqual(self.bank_journal.next_check_number, '00001051')

    def test_11_increment_is_idempotent(self):
        """Publicar dos veces el mismo número no avanza el contador dos veces."""
        self.bank_journal._increment_check_number('00001001')
        self.bank_journal._increment_check_number('00001001')
        self.assertEqual(self.bank_journal.next_check_number, '00001002')

    # ------------------------------------------------------------------
    # Mayor número de una lista
    # ------------------------------------------------------------------
    def test_20_highest_check_number(self):
        """El contador se calcula sobre el mayor número, no sobre el último de la lista."""
        highest = self.bank_journal._get_highest_check_number(
            ['00001003', '00001007', '00001005']
        )
        self.assertEqual(highest, '00001007')

    def test_21_highest_check_number_ignores_garbage(self):
        """Los valores sin parte numérica se ignoran."""
        self.assertEqual(
            self.bank_journal._get_highest_check_number(['ANULADO', '00001004', False]),
            '00001004',
        )
        self.assertFalse(self.bank_journal._get_highest_check_number(['ANULADO', False]))

    # ------------------------------------------------------------------
    # Numeración dentro de un mismo create (batch)
    # ------------------------------------------------------------------
    def test_30_batch_numbering_is_correlative(self):
        """Varias líneas creadas de una sola vez reciben números distintos."""
        numbers = []
        last = False
        for _ in range(3):
            last = self.bank_journal._next_check_number_for_batch(last)
            numbers.append(last)
        self.assertEqual(numbers, ['00001001', '00001002', '00001003'])
        self.assertEqual(len(set(numbers)), 3)

    # ------------------------------------------------------------------
    # Asignación sobre las líneas de cheque
    # ------------------------------------------------------------------
    def test_40_assign_fills_only_empty_lines(self):
        """Se completan las líneas vacías respetando las cargadas a mano."""
        checks = [self._new_check(), self._new_check('MANUAL-500'), self._new_check()]
        self.bank_journal._assign_check_numbers(checks)
        self.assertEqual(
            [c.name for c in checks],
            ['00001001', 'MANUAL-500', 'MANUAL-00000501'],
        )

    def test_41_assign_force_all_renumbers_autofilled_only(self):
        """Al cambiar de diario se recalcula lo autocompletado y se respeta lo manual."""
        checks = [
            self._new_check('00001001', '00001001'),  # autocompletado por el módulo
            self._new_check('MANUAL-500'),            # cargado a mano
        ]
        other_journal = self.env['account.journal'].create({
            'name': 'Banco Santander Test',
            'type': 'bank',
            'code': 'BST',
            'check_sequence_enabled': True,
            'next_check_number': '00009001',
            'check_number_padding': 8,
        })
        other_journal._assign_check_numbers(checks, force_all=True)
        self.assertEqual([c.name for c in checks], ['00009001', 'MANUAL-500'])

    def test_42_assign_does_nothing_when_disabled(self):
        """Con la chequera desactivada no se asigna ningún número."""
        self.bank_journal.check_sequence_enabled = False
        checks = [self._new_check()]
        self.bank_journal._assign_check_numbers(checks)
        self.assertFalse(checks[0].name)

    # ------------------------------------------------------------------
    # Restricciones
    # ------------------------------------------------------------------
    def test_50_padding_below_native_zfill_is_rejected(self):
        """l10n_latam_check hace zfill(8): un padding menor desalinearía el número."""
        with self.assertRaises(ValidationError):
            self.bank_journal.check_number_padding = 6

    def test_51_conflict_with_native_check_sequencing(self):
        """No se puede combinar con la numeración manual de account_check_printing."""
        if 'check_manual_sequencing' not in self.bank_journal._fields:
            self.skipTest('account_check_printing no está instalado')
        # La constraint se dispara al activar nuestra chequera, que es el campo
        # que agrega este módulo (check_manual_sequencing puede no existir).
        self.bank_journal.check_sequence_enabled = False
        self.bank_journal.check_manual_sequencing = True
        with self.assertRaises(ValidationError):
            self.bank_journal.check_sequence_enabled = True

    # ------------------------------------------------------------------
    # Mixin compartido
    # ------------------------------------------------------------------
    def test_60_mixin_applied_to_payment_and_register(self):
        """El pago y el wizard comparten la misma implementación de chequera."""
        self.assertIn('account.journal.check.sequence.mixin', self.env.registry)
        mixin_cls = type(self.env['account.journal.check.sequence.mixin'])
        for model in ('account.payment', 'account.payment.register'):
            model_cls = type(self.env[model])
            for method in ('_is_own_check_payment', '_use_check_sequence',
                           '_onchange_suggest_check_sequence',
                           '_onchange_l10n_latam_new_check_ids_suggest_sequence'):
                self.assertIs(
                    getattr(model_cls, method), getattr(mixin_cls, method),
                    '%s.%s debería venir del mixin, no estar duplicado' % (model, method),
                )

    def test_61_own_check_method_codes_scope(self):
        """El módulo sólo actúa sobre el método de cheque propio de la localización."""
        from odoo.addons.account_journal_check_sequence.models.check_sequence_mixin import (
            OWN_CHECK_METHOD_CODES,
        )
        self.assertEqual(OWN_CHECK_METHOD_CODES, ('own_checks',))
        self.assertNotIn('check_printing', OWN_CHECK_METHOD_CODES)
