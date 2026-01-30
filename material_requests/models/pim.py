from odoo import models, fields, api, _

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                # Simple sequence generator
                vals['name'] = self.env['ir.sequence'].next_by_code('pim') or 'PIM'
        return super(Pim, self).create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    sim_ids = fields.One2many('sim', 'pim_id', string='Purchase Requests')
    sim_count = fields.Integer(compute='_compute_sim_count', string='SIM Count')

    @api.depends('sim_ids')
    def _compute_sim_count(self):
        for record in self:
            record.sim_count = len(record.sim_ids)

    def action_process_pim(self):
        """ 
        Smart Logic: 
        1. Always create a Stock Picking for the FULL requested quantity.
           This allows Odoo to handle reservations and Backorders automatically.
        2. Check for shortages and create a SIM for missing quantities so Purchasing knows what to buy.
        """
        stock_lines = []
        sim_lines = []
        
        # Get Locations
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1) or \
                       self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        
        location_src_id = picking_type.default_location_src_id.id

        for line in self.line_ids:
            # 1. Always request the FULL amount in the Transfer
            stock_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_uom': line.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            }))
            
            # 2. Check Availability for SIM creation
            # We want to know how much we are SHORT of free stock
            product_in_loc = line.product_id.with_context(location=location_src_id)
            qty_available_free = product_in_loc.free_qty
            
            # If we need 10 and have 4 free, we need to buy 6.
            # If we need 10 and have 12 free, we need to buy 0.
            qty_shortage = max(0, line.quantity - qty_available_free)

            # 3. Prepare SIM Line if there is a shortage
            if qty_shortage > 0:
                sim_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': qty_shortage,
                }))

        # --- EXECUTE ACTIONS ---
        
        # A) Create Stock Picking (Always, if there are lines)
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
            new_picking.action_confirm() 
            # We assume 'action_assign' (Check Availability) is desired.
            # If it's not fully available, Odoo will reserve what it can and leave the rest as 'Not Available'
            new_picking.action_assign()

        # B) Create SIM (If stock missing)
        if sim_lines:
            sim_vals = {
                'pim_id': self.id,
                'line_ids': sim_lines
            }
            self.env['sim'].create(sim_vals)

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

    def action_view_sims(self):
        self.ensure_one()
        return {
            'name': _('Purchase Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'sim',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.sim_ids.ids)],
            'context': {'default_pim_id': self.id}
        }


class PimLine(models.Model):
    _name = 'pim.line'
    _description = 'PIM Material Line'

    pim_id = fields.Many2one('pim', string='PIM Reference')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)