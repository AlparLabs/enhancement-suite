from odoo import models, fields, api

class Sim(models.Model):
    _name = 'sim'
    _description = 'Solicitud Interna de Materiales (Purchase Request)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='SIM Reference', required=True, copy=False, readonly=True, default='New')
    pim_id = fields.Many2one('pim', string='Source PIM', readonly=True)
    project_id = fields.Many2one(related='pim_id.project_id', string='Project', store=True)
    partner_id = fields.Many2one('res.partner', string='Preferred Vendor', domain="[('supplier_rank', '>', 0)]")
    state = fields.Selection([
        ('draft', 'New Request'),
        ('po_created', 'PO Created'),
    ], default='draft', tracking=True)
    
    line_ids = fields.One2many('sim.line', 'sim_id', string='Missing Materials')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sim') or 'SIM'
        return super(Sim, self).create(vals_list)

    def action_create_rfq(self):
        """ 
        Converts this SIM into a Draft Purchase Order (RFQ) 
        """
        self.ensure_one()
        PurchaseOrder = self.env['purchase.order']
        
        # Determine Vendor
        partner = self.partner_id
        if not partner:
            # Try to find the first common vendor if possible, or leave empty
            # For now, we leave it empty if not set, consistent with Odoo flows 
            # where user must choose.
            pass

        # 1. Create the PO Header
        po_vals = {
            'origin': f"{self.name} ({self.pim_id.name})",
            'partner_id': partner.id if partner else False, 
            'pim_id': self.pim_id.id, 
            'sim_id': self.id,
            'order_line': []
        }

        # 2. Add the Lines
        for line in self.line_ids:
            # Try to get price from supplier info
            price_unit = 0.0
            if partner:
                supplier_info = line.product_id._select_seller(partner_id=partner, quantity=line.quantity, uom_id=line.uom_id)
                if supplier_info:
                    price_unit = supplier_info.price
            
            po_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_qty': line.quantity,
                'product_uom': line.uom_id.id,
                'price_unit': price_unit, 
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