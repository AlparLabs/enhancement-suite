from odoo import models, fields, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ('percentage_progress', 'Certificación por % de avance'),
            ('fixed_progress', 'Anticipo por % sobre monto neto'),
            ('fixed_net', 'Anticipo por Monto Fijo (Neto)'),
        ],
        ondelete={
            'percentage_progress': 'set default',
            'fixed_progress': 'set default',
            'fixed_net': 'set default',
        }
    )

    def create_invoices(self):
        if self.advance_payment_method not in ('percentage_progress', 'fixed_progress', 'fixed_net'):
            return super().create_invoices()

        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        # ── Caso 1: Certificación por % de avance ──────────────────────────────
        # Misma mecánica que el Anticipo estándar de Odoo pero con descripción
        # personalizada: "Certificación de Avance: XX%"
        if self.advance_payment_method == 'percentage_progress':
            # Llamamos al super() con el método nativo 'percentage' para que Odoo
            # cree todo correctamente (producto, contabilidad, etc).
            # Snapshot de las facturas previas para detectar las nuevas.
            invoices_before = sale_orders.mapped('invoice_ids')
            self.advance_payment_method = 'percentage'
            result = super().create_invoices()
            self.advance_payment_method = 'percentage_progress'

            # Buscamos las facturas recién creadas y renombramos sus líneas
            new_invoices = sale_orders.mapped('invoice_ids') - invoices_before
            description = _('Certificación de Avance: %s%%') % int(self.amount)
            for inv in new_invoices:
                for line in inv.invoice_line_ids:
                    if line.is_downpayment:
                        line.name = description
            return result

        # ── Caso 2: Anticipo por % sobre monto Neto ────────────────────────────
        # Idéntico al anticipo estándar pero el % se aplica sobre amount_untaxed
        # en lugar de amount_total  (Odoo por defecto usa amount_total).
        if self.advance_payment_method == 'fixed_progress':
            invoices_before = sale_orders.mapped('invoice_ids')

            # Convertimos el % sobre el neto en % equivalente sobre el total
            # para que cuando Odoo calcule (amount/100 * total) obtenga
            # exactamente (amount/100 * untaxed).
            original_method = self.advance_payment_method
            original_amount = self.amount

            # Calculamos la cantidad a facturar correctamente por cada orden
            # y generamos las facturas una a una ajustando 'amount'.
            for order in sale_orders:
                if order.amount_total:
                    # % equivalente: (pct_neto / 100 * untaxed) / total * 100
                    equivalent_pct = (original_amount / 100.0 * order.amount_untaxed) / order.amount_total * 100.0
                else:
                    equivalent_pct = original_amount

                self.advance_payment_method = 'percentage'
                self.amount = equivalent_pct
                super().create_invoices()

            self.advance_payment_method = original_method
            self.amount = original_amount

            # Renombramos líneas de las nuevas facturas
            new_invoices = sale_orders.mapped('invoice_ids') - invoices_before
            description = _('Anticipo: %s%% sobre monto neto') % int(original_amount)
            for inv in new_invoices:
                for line in inv.invoice_line_ids:
                    if line.is_downpayment:
                        line.name = description

            if self._context.get('open_invoices', False):
                return sale_orders.action_view_invoice()
            return {'type': 'ir.actions.act_window_close'}

        # ── Caso 3: Anticipo por Monto Fijo (Neto) ─────────────────────────────
        # Igual al anticipo fijo nativo pero con descripción personalizada.
        # self.fixed_amount ya es el monto neto que el usuario ingresó.
        if self.advance_payment_method == 'fixed_net':
            invoices_before = sale_orders.mapped('invoice_ids')
            self.advance_payment_method = 'fixed'
            result = super().create_invoices()
            self.advance_payment_method = 'fixed_net'

            new_invoices = sale_orders.mapped('invoice_ids') - invoices_before
            description = _('Anticipo: Monto Fijo Neto')
            for inv in new_invoices:
                for line in inv.invoice_line_ids:
                    if line.is_downpayment:
                        line.name = description
            return result