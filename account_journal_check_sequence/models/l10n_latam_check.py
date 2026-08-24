from odoo import api, models


class L10nLatamCheck(models.Model):
    _inherit = 'l10n_latam.check'

    @api.model
    def _resolve_check_sequence_payment(self, vals=None):
        """Resuelve el account.payment asociado de forma segura.

        ``active_id`` solo se considera cuando el contexto declara que el
        modelo activo es account.payment: de lo contrario podría pertenecer a
        cualquier otro registro abierto y sugeriríamos el número de un diario
        equivocado (o directamente romperíamos con MissingError).
        """
        context = self.env.context
        payment_id = (vals or {}).get('payment_id') or context.get('default_payment_id')
        if not payment_id and context.get('active_model') == 'account.payment':
            payment_id = context.get('active_id')
        if not payment_id:
            return self.env['account.payment']
        return self.env['account.payment'].browse(payment_id).exists()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'name' in fields_list and not res.get('name'):
            payment = self._resolve_check_sequence_payment(res)
            journal = payment and payment._check_sequence_journal()
            if journal:
                res['name'] = journal._get_next_check_number_formatted()
        return res

    @api.onchange('payment_id')
    def _onchange_payment_id_suggest_check_sequence(self):
        for rec in self.filtered(lambda check: not check.name):
            payment = rec.payment_id or rec._resolve_check_sequence_payment()
            journal = payment and payment._check_sequence_journal()
            if journal:
                rec.name = journal._get_next_check_number_formatted()

    @api.model_create_multi
    def create(self, vals_list):
        """Numera los cheques creados sin nombre, encadenando el correlativo.

        Se contemplan tanto los números ya asignados en este mismo lote como
        los de las líneas hermanas ya existentes en el pago, de modo que un
        create múltiple no repita el mismo número en todas las líneas.
        """
        assigned_by_payment = {}
        for vals in vals_list:
            payment = self._resolve_check_sequence_payment(vals)
            journal = payment and payment._check_sequence_journal()
            if not journal:
                continue
            if payment.id not in assigned_by_payment:
                assigned_by_payment[payment.id] = [
                    check.name for check in payment.l10n_latam_new_check_ids if check.name
                ]
            already_used = assigned_by_payment[payment.id]
            if vals.get('name'):
                already_used.append(vals['name'])
                continue
            start_from = journal._get_highest_check_number(already_used) if already_used else False
            vals['name'] = journal._peek_check_numbers(1, start_from=start_from)[0]
            already_used.append(vals['name'])
        return super().create(vals_list)
