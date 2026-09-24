from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

MANAGER_GROUP = 'purchase.group_purchase_manager'


class CommercialConditionsAccessMixin(models.AbstractModel):
    """Restringe la edición de condiciones comerciales a gerentes de compras.

    Cada modelo que lo hereda declara en `_commercial_condition_fields` qué
    campos protege. La vista usa `can_edit_commercial_conditions` para el
    `readonly`; el servidor valida en create/write.
    """
    _name = 'commercial.conditions.access.mixin'
    _description = 'Permiso de edición de condiciones comerciales'

    _commercial_condition_fields: tuple[str, ...] = ()

    can_edit_commercial_conditions = fields.Boolean(
        compute='_compute_can_edit_commercial_conditions',
    )

    @api.depends_context('uid')
    def _compute_can_edit_commercial_conditions(self) -> None:
        allowed = self.env.user.has_group(MANAGER_GROUP)
        for rec in self:
            rec.can_edit_commercial_conditions = allowed

    def _check_commercial_conditions_access(self, vals_list: list[dict]) -> None:
        if self.env.su or self.env.user.has_group(MANAGER_GROUP):
            return
        touched = {
            field for vals in vals_list for field in vals
            if field in self._commercial_condition_fields
        }
        if touched:
            raise AccessError(_(
                'Sólo los gerentes de compras pueden modificar condiciones '
                'comerciales (%s).', ', '.join(sorted(touched)),
            ))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_commercial_conditions_access(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._check_commercial_conditions_access([vals])
        return super().write(vals)
