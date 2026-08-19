from odoo import api, fields, models


class L10nLatamCheck(models.Model):
    _inherit = 'l10n_latam.check'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'name' in fields_list and not res.get('name'):
            payment_id = res.get('payment_id') or self.env.context.get('default_payment_id') or self.env.context.get('active_id')
            if payment_id:
                payment = self.env['account.payment'].browse(payment_id)
                if payment and payment._is_own_check_payment() and payment.journal_id and payment.journal_id.check_sequence_enabled:
                    res['name'] = payment.journal_id._get_next_check_number_formatted()
        return res

    @api.onchange('payment_id')
    def _onchange_payment_id_suggest_check_sequence(self):
        for rec in self:
            if not rec.name:
                payment = rec.payment_id or (
                    rec.env.context.get('default_payment_id')
                    and rec.env['account.payment'].browse(rec.env.context.get('default_payment_id'))
                )
                if payment and payment._is_own_check_payment() and payment.journal_id and payment.journal_id.check_sequence_enabled:
                    rec.name = payment.journal_id._get_next_check_number_formatted()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('payment_id'):
                payment = self.env['account.payment'].browse(vals['payment_id'])
                if payment and payment._is_own_check_payment() and payment.journal_id and payment.journal_id.check_sequence_enabled:
                    vals['name'] = payment.journal_id._get_next_check_number_formatted()
        return super().create(vals_list)
