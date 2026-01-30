from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SimMergeWizard(models.TransientModel):
    _name = 'sim.merge.wizard'
    _description = 'Merge SIMs into one PO'

    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, domain="[('supplier_rank', '>', 0)]")
    sim_ids = fields.Many2many('sim', string='Selected SIMs')

    def action_merge(self):
        self.ensure_one()
        if not self.sim_ids:
            return
        
        PurchaseOrder = self.env['purchase.order']
        
        # 1. Prepare PO Header
        # We consolidate origins
        origins = [s.name for s in self.sim_ids]
        combined_origin = ", ".join(origins)
        
        po_vals = {
            'partner_id': self.partner_id.id,
            'origin': combined_origin,
            'sim_ids': [fields.Command.set(self.sim_ids.ids)],
            'order_line': []
        }

        # 2. Consolidate Lines
        # We want to merge lines for the same product? 
        # For now, let's just append them. Merging logic can be complex (different UoMs, etc).
        # Standard Odoo behavior usually appends. If we want to merge, we need a dict.
        
        # Let's try to merge if product matches (and UoM matches)
        merged_lines = {} # key: product_id, value: {qty, uom, price}

        for sim in self.sim_ids:
            if sim.state != 'draft':
                raise UserError(_("One of the selected SIMs is already processed: %s") % sim.name)

            for line in sim.line_ids:
                key = line.product_id.id
                if key not in merged_lines:
                    # Get price
                    price_unit = 0.0
                    supplier_info = line.product_id._select_seller(partner_id=self.partner_id, quantity=line.quantity, uom_id=line.uom_id)
                    if supplier_info:
                        price_unit = supplier_info.price

                    merged_lines[key] = {
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'product_qty': line.quantity,
                        'product_uom': line.uom_id.id,
                        'price_unit': price_unit,
                    }
                else:
                    # Increment Qty
                    merged_lines[key]['product_qty'] += line.quantity
        
        # Convert merged_lines to ORM commands
        for key, val in merged_lines.items():
            po_vals['order_line'].append((0, 0, {
                'product_id': val['product_id'],
                'name': val['name'],
                'product_qty': val['product_qty'],
                'product_uom': val['product_uom'],
                'price_unit': val['price_unit'],
                'date_planned': fields.Date.context_today(self),
            }))

        # 3. Create PO
        new_po = PurchaseOrder.create(po_vals)
        
        # 4. Update SIMs status
        self.sim_ids.write({'state': 'po_created'})
        
        return {
            'name': 'Request for Quotation',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': new_po.id,
            'view_mode': 'form',
        }
