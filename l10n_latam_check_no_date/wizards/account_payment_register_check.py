from odoo import fields, models


class L10nLatamCheckPaymentRegisterCheck(models.TransientModel):
    """
    Override del wizard l10n_latam.payment.register.check para hacer el campo
    payment_date opcional al registrar un cheque propio desde el wizard de pago.
    """
    _inherit = 'l10n_latam.payment.register.check'

    payment_date = fields.Date(
        string='Fecha del Cheque',
        readonly=False,
        required=False,  # Override: quitar obligatoriedad del wizard
        help="Fecha escrita en el cheque. Puede dejarse vacía si el cheque "
             "se emite sin fecha.",
    )
