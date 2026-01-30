from odoo import models, fields, api

class Project(models.Model):
    _inherit = 'project.project'

    pim_ids = fields.One2many('pim', 'project_id', string='Material Requests')
    pim_count = fields.Integer(compute='_compute_pim_count', string='PIM Count')

    @api.depends('pim_ids')
    def _compute_pim_count(self):
        for project in self:
            project.pim_count = len(project.pim_ids)

    def action_view_pims(self):
        self.ensure_one()
        return {
            'name': 'Material Requests',
            'type': 'ir.actions.act_window',
            'res_model': 'pim',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id}
        }
