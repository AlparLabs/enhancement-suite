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
        # Notify Inventory Managers
        group_stock_manager = self.env.ref('stock.group_stock_manager')
        users = group_stock_manager.users
        for user in users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                note=_('Please review this Material Request and decide to Deliver or Buy.')
            )

    def action_approve(self):
        self.write({'state': 'approved'})

    sim_ids = fields.One2many('sim', 'pim_id', string='Purchase Requests')
    sim_count = fields.Integer(compute='_compute_sim_count', string='SIM Count')

    @api.depends('sim_ids')
    def _compute_sim_count(self):
        for record in self:
            record.sim_count = len(record.sim_ids)

    def action_create_transfer(self):
        """ 
        Create a Stock Picking for the FULL requested quantity.
        """
        self.ensure_one()
        stock_lines = []
        
        # Get Locations
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1) or \
                       self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        
        for line in self.line_ids:
            stock_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_uom': line.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            }))
            
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
            new_picking.action_assign()
        
        # We don't change state to processing automatically anymore, as they might need to do both actions.
        # But if we want to track progress, maybe we can check if both are done? 
        # For now, let's set it to processing if at least one action is taken.
        if self.state == 'submitted':
            self.write({'state': 'processing'})

    def action_create_sim(self):
        """
        Check for shortages and create a SIM for missing quantities.
        """
        self.ensure_one()
        sim_lines = []
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1) or \
                       self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        location_src_id = picking_type.default_location_src_id.id

        for line in self.line_ids:
            # Check shortage based on free qty in the source location
            product_in_loc = line.product_id.with_context(location=location_src_id)
            qty_available_free = product_in_loc.free_qty
            qty_shortage = max(0, line.quantity - qty_available_free)

            if qty_shortage > 0:
                sim_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': qty_shortage,
                }))

        if sim_lines:
            sim_vals = {
                'pim_id': self.id,
                'line_ids': sim_lines
            }
            self.env['sim'].create(sim_vals)
            
        if self.state == 'submitted':
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
    qty_available = fields.Float(string='On Hand (Free)', compute='_compute_qty_available')

    @api.depends('product_id')
    def _compute_qty_available(self):
        for line in self:
            if line.product_id:
                # We can try to guess the warehouse/location from context or default
                # Ideally, we should use the same logic as in the actions (picking type's source location)
                # For simplicity here, we use the standard 'free_qty' which usually looks at default warehouse.
                line.qty_available = line.product_id.free_qty
            else:
                line.qty_available = 0.0