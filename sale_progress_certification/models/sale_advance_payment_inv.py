from odoo import models, fields, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('percentage_progress', 'Certificación por % de avance'),
            ('fixed_net', 'Anticipo por Monto Fijo (Neto)'),
        ],
        ondelete={
            'percentage_progress': 'set default',
            'fixed_net': 'set default',
        }
    )

    def create_invoices(self):
        if self.advance_payment_method not in ('percentage_progress', 'fixed_net'):
            return super().create_invoices()

        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        # ── Caso 1: Certificación por % de avance ──────────────────────────────
        # Misma mecánica que el anticipo estándar de Odoo pero con descripción
        # personalizada: "Certificación de Avance: XX%"
        if self.advance_payment_method == 'percentage_progress':
            invoices_before = sale_orders.mapped('invoice_ids')
            pct = int(self.amount)
            self.write({'advance_payment_method': 'percentage'})
            try:
                result = super().create_invoices()
            finally:
                self.write({'advance_payment_method': 'percentage_progress'})

            new_invoices = sale_orders.mapped('invoice_ids') - invoices_before
            description = _('Certificación de Avance: %s%%') % pct
            for inv in new_invoices:
                for line in inv.invoice_line_ids:
                    if line.is_downpayment:
                        line.name = description
            return result

        # ── Caso 2: Anticipo por Monto Fijo (Neto) ─────────────────────────────
        # Odoo trata fixed_amount como monto TOTAL (impuestos incluidos) y
        # retrocede price_unit = fixed_amount / (1+tasa).
        # Aquí el usuario ingresa el monto NETO; los impuestos se suman encima.
        # Por eso restauramos price_unit al neto original tras la creación.
        if self.advance_payment_method == 'fixed_net':
            net_amount = self.fixed_amount
            invoices_before = sale_orders.mapped('invoice_ids')
            self.write({'advance_payment_method': 'fixed'})
            try:
                result = super().create_invoices()
            finally:
                self.write({'advance_payment_method': 'fixed_net'})

            new_invoices = sale_orders.mapped('invoice_ids') - invoices_before
            description = _('Anticipo: Monto Fijo Neto')
            for inv in new_invoices:
                for line in inv.invoice_line_ids:
                    if line.is_downpayment:
                        line.name = description
                        line.price_unit = net_amount
            return result
