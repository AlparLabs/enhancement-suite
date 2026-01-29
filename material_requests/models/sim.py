from odoo import models, fields, api

class Sim(models.Model):
    _name = 'sim'
    _description = 'Solicitud Interna de Materiales (Purchase Request)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='SIM Reference', required=True, copy=False, readonly=True, default='New')
    pim_id = fields.Many2one('pim', string='Source PIM', readonly=True)
    project_id = fields.Many2one(related='pim_id.project_id', string='Project', store=True)
    state = fields.Selection([
        ('draft', 'New Request'),
        ('po_created', 'PO Created'),
    ], default='draft', tracking=True)
    
    line_ids = fields.One2many('sim.line', 'sim_id', string='Missing Materials')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sim') or 'SIM'
        return super(Sim, self).create(vals)

    def action_create_rfq(self):
        """ 
        Converts this SIM into a Draft Purchase Order (RFQ) 
        """
        self.ensure_one()
        PurchaseOrder = self.env['purchase.order']
        
        # 1. Create the PO Header
        po_vals = {
            'origin': f"{self.name} ({self.pim_id.name})",
            'partner_id': self.env.user.company_id.partner_id.id, # Placeholder Vendor (User must change it)
            'pim_id': self.pim_id.id, # Custom link we will add to PO
            'order_line': []
        }

        # 2. Add the Lines
        for line in self.line_ids:
            po_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_qty': line.quantity,
                'product_uom': line.uom_id.id,
                'price_unit': 0.0, # To be filled by buyer
                'date_planned': fields.Date.context_today(self),
            }))
        
        # 3. Create PO and Open it
        new_po = PurchaseOrder.create(po_vals)
        self.state = 'po_created'
        
        return {
            'name': 'Request for Quotation',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': new_po.id,
            'view_mode': 'form',
        }

class SimLine(models.Model):
    _name = 'sim.line'
    _description = 'SIM Material Line'

    sim_id = fields.Many2one('sim', string='SIM')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Qty to Buy', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM', related='product_id.uom_id')