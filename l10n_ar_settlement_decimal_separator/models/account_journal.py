from odoo import fields, models

# Tipos de liquidación cuyo TXT es seguro de reemplazar carácter por carácter.
#
# El reemplazo se aplica sobre el contenido completo del archivo, así que un
# tipo solo puede sumarse acá después de verificar que su formato no tiene
# campos de texto libre. En SICORE todos los campos son numéricos o fechas con
# "/", de modo que el único "." presente es el separador decimal. Otros TXT del
# mismo dispatch sí escriben nombre y domicilio del contacto (por ejemplo
# l10n_ar_txt_sire), y un reemplazo global corrompería "ACME S.A." o
# "Av. Rivadavia 1234".
L10N_AR_SEPARATOR_SAFE_SETTLEMENTS = ["sicore_aplicado"]


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ar_txt_decimal_separator = fields.Selection(
        [(".", "Punto (.)"), (",", "Coma (,)")],
        string="Separador decimal del TXT",
        default=".",
        help="Separador decimal con el que se generan los importes del archivo TXT. "
        "Debe coincidir con el configurado en el aplicativo que va a importarlo. "
        "En el SICORE se define en Importar/Exportar Retenciones/Percepciones → "
        "Configuración de Importación de Retenciones.",
    )

    def get_tax_settlement_files_values(self, move_lines):
        """Aplica el separador decimal configurado al TXT generado por el módulo base.

        El ancho fijo del registro se preserva por construcción: el reemplazo es
        de un carácter por otro. ``txt_filename`` no se toca nunca, porque el
        nombre del archivo lleva un punto en la extensión.
        """
        files_values = super().get_tax_settlement_files_values(move_lines)
        separator = self.l10n_ar_txt_decimal_separator or "."
        if separator == "." or self.settlement_tax not in L10N_AR_SEPARATOR_SAFE_SETTLEMENTS:
            return files_values
        for values in files_values:
            content = values.get("txt_content")
            if isinstance(content, str):
                values["txt_content"] = content.replace(".", separator)
        return files_values
