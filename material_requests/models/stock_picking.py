from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # This field stores the link back to the PIM
    pim_id = fields.Many2one('pim', string='Origin PIM', readonly=True)

    def _action_done(self):
        """
        Override to notify the Project Manager (PIM Requester) when materials are delivered.
        """
        res = super(StockPicking, self)._action_done()
        for picking in self:
            if picking.pim_id:
                # Post message on PIM
                picking.pim_id.message_post(
                    body=f"Materiales entregados en transferencia: <a href=# data-oe-model=stock.picking data-oe-id={picking.id}>{picking.name}</a>",
                    subtype_xmlid="mail.mt_comment",
                    partner_ids=[picking.pim_id.user_id.partner_id.id]
                )
        return res