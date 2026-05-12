from odoo import fields, models


class L10nLatamCheck(models.Model):
    """
    Override del modelo l10n_latam.check para hacer el campo payment_date
    opcional en cheques propios (own_checks).

    En la implementación original, payment_date = required=True, lo que impide
    registrar un cheque propio sin fecha. Este override lo hace opcional,
    permitiendo que el pago contable tenga su fecha mientras el cheque
    puede quedar sin fecha de pago escrita.
    """
    _inherit = 'l10n_latam.check'

    payment_date = fields.Date(
        string='Fecha del Cheque',
        readonly=False,
        required=False,  # Override: quitar obligatoriedad
        help="Fecha escrita en el cheque. Puede dejarse vacía si el cheque "
             "se emite sin fecha. La fecha contable del pago no se ve afectada.",
    )
