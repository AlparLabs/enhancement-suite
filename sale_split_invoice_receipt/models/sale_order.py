from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_view_invoice(self):
        """
        Sobrescribimos la acción del botón inteligente para incluir Recibos (out_receipt)
        en la lista de documentos, no solo Facturas.
        """
        # 1. Ejecutamos la lógica original para obtener la estructura base de la acción
        action = super(SaleOrder, self).action_view_invoice()
        
        # 2. Buscamos TODOS los movimientos vinculados a este pedido
        # (La lógica estándar a veces filtra por tipo, así que hacemos nuestra propia búsqueda)
        invoices = self.env['account.move'].search([
            ('line_ids.sale_line_ids.order_id', 'in', self.ids),
            ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')) # Agregamos out_receipt
        ])

        # 3. Actualizamos el dominio y los contextos de la acción
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.id
        else:
            action['domain'] = [('id', 'in', invoices.ids)]

        # 4. Aseguramos que el contexto no filtre por defecto
        # (A veces Odoo pone default_move_type='out_invoice' que puede molestar al crear uno nuevo desde ahí,
        # pero para ver listados está bien).
        return action