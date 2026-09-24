from __future__ import annotations

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    supplier_pricelist_import_count = fields.Integer(
        compute='_compute_supplier_pricelist_import_count',
    )

    def _compute_supplier_pricelist_import_count(self) -> None:
        data = self.env['supplier.pricelist.import']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count'],
        )
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.supplier_pricelist_import_count = counts.get(partner.id, 0)

    def action_view_supplier_pricelist_imports(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Listas importadas',
            'res_model': 'supplier.pricelist.import',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
