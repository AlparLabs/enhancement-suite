from odoo import models, fields, api

class Pim(models.Model):
    _name = 'pim'
    _description = 'Internal Material Request (PIM)'
    _inherit = ['mail.thread', 'mail.activity.mixin'] # Enables Chatter & Activities

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    project_id = fields.Many2one('project.project', string='Project', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user, tracking=True)
    date_required = fields.Date(string='Date Required', default=fields.Date.context_today, tracking=True)
    
    # The Workflow State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many('pim.line', 'pim_id', string='Materials')
    picking_ids = fields.One2many('stock.picking', 'pim_id', string='Transfers')
    picking_count = fields.Integer(compute='_compute_picking_count', string='Transfer Count')

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            # Simple sequence generator
            vals['name'] = self.env['ir.sequence'].next_by_code('pim') or 'PIM'
        return super(Pim, self).create(vals)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_process_pim(self):
        """ 
        1. Checks stock availability.
        2. Creates a Transfer (Picking) for available items.
        3. Moves state to 'Processing'.
        """
        stock_lines = []
        
        # We need the Warehouse Output location (Standard: Stock -> Customers/Project)
        # For this example, we grab the default warehouse locations.
        # In a real setup, you might want to pick specific Source/Dest locations.
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            # Fallback if no internal type found, usually unlikely in standard Odoo
             picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

        for line in self.line_ids:
            # Check 'Free To Use' quantity (Quantity on Hand - Reserved)
            qty_available = line.product_id.free_qty
            
            # Logic: If we have ANY stock, we create a transfer for it.
            # If we need 10 and have 4, we transfer 4. The other 6 will become a SIM later.
            qty_to_transfer = 0
            if qty_available >= line.quantity:
                qty_to_transfer = line.quantity
            elif qty_available > 0:
                qty_to_transfer = qty_available
            
            if qty_to_transfer > 0:
                stock_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.name,
                    'product_uom': line.uom_id.id,
                    'product_uom_qty': qty_to_transfer,
                    'location_id': picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                }))

        # Create the Picking (Document) if there are items to move
        if stock_lines:
            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'origin': self.name,
                'pim_id': self.id,
                'move_ids_without_package': stock_lines
            }
            new_picking = self.env['stock.picking'].create(picking_vals)
            
            # Auto-Confirm: This Reserves the stock so nobody else takes it.
            new_picking.action_confirm()
            new_picking.action_assign() # Checks availability formally in Odoo

        self.write({'state': 'processing'})

    # Smart Button Action
    def action_view_pickings(self):
        self.ensure_one()
        return {
            'name': _('Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'default_pim_id': self.id}
        }


class PimLine(models.Model):
    _name = 'pim.line'
    _description = 'PIM Material Line'

    pim_id = fields.Many2one('pim', string='PIM Reference')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)