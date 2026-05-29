from __future__ import annotations

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    divergence_threshold_warning: float = fields.Float(
        string='Umbral de alerta de divergencia (%)',
        default=10.0,
        config_parameter='alpardata_purchase_reference_cost.divergence_threshold_warning',
        help=(
            'Si la diferencia entre el Precio de Coste (AVCO) y el Costo de Referencia '
            'supera este porcentaje, se muestra una alerta visual amarilla en el listado '
            'de productos.'
        ),
    )

    divergence_threshold_critical: float = fields.Float(
        string='Umbral crítico de divergencia (%)',
        default=25.0,
        config_parameter='alpardata_purchase_reference_cost.divergence_threshold_critical',
        help=(
            'Si la diferencia entre el Precio de Coste (AVCO) y el Costo de Referencia '
            'supera este porcentaje, se muestra una alerta crítica roja en el listado '
            'de productos.'
        ),
    )
