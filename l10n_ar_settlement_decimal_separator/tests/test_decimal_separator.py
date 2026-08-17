from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Un registro SICORE real, campo por campo, tal como lo arma
# l10n_ar_account_tax_settlement.sicore_aplicado_files_values. Los únicos "."
# del registro son los cuatro separadores decimales; las fechas usan "/" y el
# resto de los campos numéricos son enteros con padding de ceros.
SICORE_FIELDS = [
    "02",                     # codigo de comprobante          [ 2]
    "15/06/2026",             # fecha emision comprobante      [10]
    "0000000000012345",       # numero comprobante             [16]
    "%016.2f" % 121000.50,    # importe del comprobante        [16] <- decimal
    "0217",                   # codigo de impuesto             [ 4]
    "078",                    # codigo de regimen              [ 3]
    "1",                      # codigo de operacion            [ 1]
    "%014.2f" % 100000.00,    # base de calculo                [14] <- decimal
    "15/06/2026",             # fecha emision retencion        [10]
    "01",                     # codigo de condicion            [ 2]
    "0",                      # retencion a sujeto suspendido  [ 1]
    "%014.2f" % 2100.00,      # importe de la retencion        [14] <- decimal
    "%06.2f" % 0.0,           # porcentaje de exclusion        [ 6] <- decimal
    "15/06/2026",             # fecha emision boletin          [10]
    "80",                     # tipo documento retenido        [ 2]
    "30712345678".ljust(20),  # numero documento retenido      [20]
    "%014d" % 0,              # numero certificado original    [14]
]
SICORE_RECORD = "".join(SICORE_FIELDS)
SICORE_RECORD_WIDTH = 145
SICORE_CONTENT = (SICORE_RECORD + "\r\n") * 2
SICORE_FILENAME = "SICORE Aplicado.txt"


@tagged("post_install", "-at_install")
class TestSettlementDecimalSeparator(TransactionCase):
    """El módulo transforma el resultado del dispatch del módulo base.

    Los tests parchean el generador concreto (``sicore_aplicado_files_values``)
    con un contenido SICORE fijo en lugar de construir toda la cadena de
    retenciones de la localización argentina. Lo que se está verificando es la
    transformación y sus guardas, no la generación del TXT, que es
    responsabilidad de l10n_ar_account_tax_settlement.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.no_lines = cls.env["account.move.line"]
        cls.journal = cls.env["account.journal"].create({
            "name": "Liquidación SICORE (test)",
            "code": "TSICO",
            "type": "general",
            "tax_settlement": "yes",
            "settlement_tax": "sicore_aplicado",
        })

    def setUp(self):
        super().setUp()
        self.assertEqual(len(SICORE_RECORD), SICORE_RECORD_WIDTH)

    def _patch_generator(self, method_name, files_values):
        """Reemplaza el generador del módulo base por un contenido fijo."""
        def _fake(journal, move_lines):
            return [dict(values) for values in files_values]

        self.patch(type(self.env["account.journal"]), method_name, _fake)

    def _patch_sicore(self):
        self._patch_generator(
            "sicore_aplicado_files_values",
            [{"txt_filename": SICORE_FILENAME, "txt_content": SICORE_CONTENT}],
        )

    def test_default_separator_leaves_content_untouched(self):
        """Con el valor por defecto el contenido es idéntico al de super().

        Éste es el test de regresión: instalar el módulo no puede cambiar la
        salida de ninguna instancia existente.
        """
        self._patch_sicore()
        self.assertEqual(self.journal.l10n_ar_txt_decimal_separator, ".")

        files_values = self.journal.get_tax_settlement_files_values(self.no_lines)

        self.assertEqual(files_values[0]["txt_content"], SICORE_CONTENT)

    def test_null_separator_behaves_like_dot(self):
        """Los diarios preexistentes quedan en NULL y se tratan como punto."""
        self._patch_sicore()
        self.journal.l10n_ar_txt_decimal_separator = False

        files_values = self.journal.get_tax_settlement_files_values(self.no_lines)

        self.assertEqual(files_values[0]["txt_content"], SICORE_CONTENT)

    def test_comma_replaces_every_decimal_point(self):
        """Con coma no queda ningún punto y aparecen 4 comas por registro."""
        self._patch_sicore()
        self.journal.l10n_ar_txt_decimal_separator = ","

        files_values = self.journal.get_tax_settlement_files_values(self.no_lines)
        content = files_values[0]["txt_content"]

        self.assertNotIn(".", content)
        for record in content.split("\r\n")[:-1]:
            self.assertEqual(record.count(","), 4)

    def test_comma_preserves_fixed_record_width(self):
        """El ancho fijo del registro se mantiene: se cambia un carácter por otro."""
        self._patch_sicore()
        self.journal.l10n_ar_txt_decimal_separator = ","

        files_values = self.journal.get_tax_settlement_files_values(self.no_lines)
        content = files_values[0]["txt_content"]

        self.assertEqual(len(content), len(SICORE_CONTENT))
        for record in content.split("\r\n")[:-1]:
            self.assertEqual(len(record), SICORE_RECORD_WIDTH)

    def test_settlement_tax_outside_whitelist_is_untouched(self):
        """Un TXT con texto libre no se toca aunque el diario esté en coma.

        iibb_sufrido (SIFERE) escribe razón social y domicilio del contacto: un
        reemplazo global corrompería "ACME S.A." o "Av. Rivadavia 1234".
        """
        sifere_content = "ACME S.A.       Av. Rivadavia 1234\r\n"
        self._patch_generator(
            "iibb_sufrido_files_values",
            [{"txt_filename": "SIFERE.txt", "txt_content": sifere_content}],
        )
        self.journal.settlement_tax = "iibb_sufrido"
        self.journal.l10n_ar_txt_decimal_separator = ","

        files_values = self.journal.get_tax_settlement_files_values(self.no_lines)

        self.assertEqual(files_values[0]["txt_content"], sifere_content)

    def test_filename_is_never_modified(self):
        """El nombre del archivo lleva un punto en la extensión y no se toca."""
        self._patch_sicore()

        for separator in (".", False, ","):
            with self.subTest(separator=separator):
                self.journal.l10n_ar_txt_decimal_separator = separator
                files_values = self.journal.get_tax_settlement_files_values(self.no_lines)
                self.assertEqual(files_values[0]["txt_filename"], SICORE_FILENAME)
