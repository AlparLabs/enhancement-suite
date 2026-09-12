# -*- coding: utf-8 -*-
from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    b2b_is_account_payment = fields.Boolean(
        string="Pago a Cuenta B2B",
        copy=False,
        help="Indica si esta transacción fue iniciada como un pago o anticipo a cuenta corriente desde la intranet B2B."
    )
