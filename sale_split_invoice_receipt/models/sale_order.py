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
            # FIX: Si super() encontró solo 1 factura, habrá seteado res_id y views=[(form, 'form')].
            # Nosotros encontramos más (ej. 1 factura + 1 recibo), así que forzamos lista.
            action['res_id'] = False
            action['views'] = [
                (self.env.ref('account.view_out_invoice_list').id, 'list'),
                (self.env.ref('account.view_move_form').id, 'form')
            ]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.id
        else:
            action['domain'] = [('id', 'in', invoices.ids)]

        # 4. Aseguramos que el contexto no filtre por defecto
        # Eliminamos default_move_type para que no filtre en la vista de lista
        if 'default_move_type' in action['context']:
            context = dict(action['context'])
            context.pop('default_move_type', None)
            action['context'] = context

        return action