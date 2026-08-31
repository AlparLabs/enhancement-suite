from __future__ import annotations

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ── Costo de referencia comercial ────────────────────────────────────────
    reference_cost: float = fields.Float(
        string='Costo de referencia',
        digits='Product Price',
        compute='_compute_reference_cost',
        store=False,
        help=(
            'Calculado automáticamente desde el Costo de Referencia del '
            'proveedor principal vigente (menor sequence, fecha válida hoy). '
            'Actualizalo cargando una nueva lista de precios del proveedor.'
        ),
    )

    # ── Indicador de divergencia vs AVCO ─────────────────────────────────────
    cost_divergence_pct: float = fields.Float(
        string='Divergencia AVCO vs Referencia (%)',
        compute='_compute_cost_divergence',
        store=False,
        help=(
            'Diferencia porcentual entre el Precio de Coste (AVCO) y el '
            'Costo de Referencia. Si supera el umbral configurado en '
            'Ajustes, aparece un indicador visual de alerta.'
        ),
    )

    cost_divergence_alert: str = fields.Selection(
        selection=[
            ('ok', 'OK'),
            ('warning', 'Atención'),
            ('critical', 'Crítico'),
        ],
        string='Estado de divergencia',
        compute='_compute_cost_divergence',
        store=False,
    )

    cost_schedule_count: int = fields.Integer(
        string='Programaciones pendientes',
        compute='_compute_cost_schedule_count',
    )

    cost_history_count: int = fields.Integer(
        string='Historial de precios por proveedor',
        compute='_compute_cost_history_count',
    )

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends(
        'uom_id',
        'seller_ids.reference_cost',
        'seller_ids.date_start',
        'seller_ids.date_end',
        'seller_ids.sequence',
        'seller_ids.company_id',
        'seller_ids.product_uom_id',
    )
    @api.depends_context('company')
    def _compute_reference_cost(self) -> None:
        """
        Delega en `_get_reference_cost_seller()`, el mismo resolver que usa la
        línea de compra: así la ficha de producto y la orden nunca muestran
        costos distintos.

        El campo no se almacena a propósito: el resolver depende de la empresa
        activa (jerarquía sucursal → matriz → global) y de la fecha de hoy, dos
        cosas que no son datos almacenados. Con store=True el valor guardado
        dependería de quién dispara el recálculo y quedaría desactualizado al
        cruzarse una fecha de vigencia.
        """
        for tmpl in self:
            tmpl.reference_cost = tmpl._reference_cost_in_uom(
                tmpl._get_reference_cost_seller()
            )

    def _reference_cost_in_uom(self, seller, uom=None) -> float:
        """Costo de referencia de `seller` expresado en `uom`.

        El costo de referencia se carga en la unidad de compra del proveedor,
        que no tiene por que ser la del producto (ej: se compra por "Packs x
        24" y se stockea por "Unidades"). Sin convertir, el precio por pack
        terminaria cargado como precio por unidad.

        Es la misma conversion que hace el core con `seller.price` en
        `product.supplierinfo::_compute_price_discounted`. Por defecto convierte
        a la unidad del producto, que es la unidad en la que esta expresado
        `standard_price` — asi el semaforo de divergencia AVCO vs referencia
        compara dos valores en la misma unidad.
        """
        self.ensure_one()
        if not seller or seller.reference_cost <= 0:
            return 0.0
        target = uom or self.uom_id
        source = seller.product_uom_id
        if not source or not target or source == target:
            return seller.reference_cost
        return source._compute_price(seller.reference_cost, target)

    def _get_reference_cost_seller(self, partner=None):
        """Devuelve el `product.supplierinfo` vigente con mejor ranking para la
        empresa activa.

        Ranking: empresa más específica primero (la activa y sus matrices,
        recorriendo `parent_id`), luego los proveedores globales (sin empresa)
        y, dentro de cada nivel, por `sequence`. Solo considera registros con
        `reference_cost > 0` y fecha válida hoy.

        Si se pasa `partner`, restringe al proveedor indicado (comparando por
        `commercial_partner_id`). La línea de compra lo usa así para respetar el
        proveedor cargado en la orden sin perder la jerarquía de empresas.
        """
        self.ensure_one()
        today = fields.Date.today()
        preferred_ids = []
        company = self.env.company
        while company:
            preferred_ids.append(company.id)
            company = company.parent_id
        rank = {cid: idx for idx, cid in enumerate(preferred_ids)}
        global_rank = len(preferred_ids)

        def _sort_key(seller):
            if seller.company_id:
                company_rank = rank.get(seller.company_id.id, global_rank)
            else:
                company_rank = global_rank
            return (company_rank, seller.sequence, seller._origin.id or 0)

        commercial = partner.commercial_partner_id if partner else None
        candidates = self.sudo().seller_ids.filtered(
            lambda s: s.reference_cost > 0
            and (not s.date_start or s.date_start <= today)
            and (not s.date_end or s.date_end >= today)
            and (not s.company_id or s.company_id.id in rank)
            and (commercial is None or s.partner_id.commercial_partner_id == commercial)
        )
        ordered = candidates.sorted(key=_sort_key)
        return ordered[0] if ordered else self.env['product.supplierinfo']

    @api.depends('standard_price', 'reference_cost')
    def _compute_cost_divergence(self) -> None:
        threshold_warning = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'alpardata_purchase_reference_cost.divergence_threshold_warning', 10.0
            )
        )
        threshold_critical = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'alpardata_purchase_reference_cost.divergence_threshold_critical', 25.0
            )
        )
        for rec in self:
            if not rec.reference_cost:
                rec.cost_divergence_pct = 0.0
                rec.cost_divergence_alert = 'ok'
                continue
            divergence = abs(
                (rec.standard_price - rec.reference_cost) / rec.reference_cost * 100
            )
            rec.cost_divergence_pct = divergence
            if divergence >= threshold_critical:
                rec.cost_divergence_alert = 'critical'
            elif divergence >= threshold_warning:
                rec.cost_divergence_alert = 'warning'
            else:
                rec.cost_divergence_alert = 'ok'

    @api.depends_context('company')
    def _compute_cost_schedule_count(self) -> None:
        for rec in self:
            rec.cost_schedule_count = self.env['product.cost.schedule'].search_count([
                ('product_tmpl_id', '=', rec.id),
                ('state', 'in', ('draft', 'scheduled')),
            ])

    @api.depends_context('company')
    def _compute_cost_history_count(self) -> None:
        for rec in self:
            rec.cost_history_count = self.env[
                'product.supplierinfo.cost.history'
            ].search_count([('product_tmpl_id', '=', rec.id)])

    # ── Acciones de smart buttons ─────────────────────────────────────────────

    def action_view_cost_schedules(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Programaciones de costo',
            'res_model': 'product.cost.schedule',
            'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }

    def action_view_cost_history(self) -> dict:
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Historial de precios por proveedor',
            'res_model': 'product.supplierinfo.cost.history',
            'view_mode': 'list',
            'domain': [('product_tmpl_id', '=', self.id)],
        }
