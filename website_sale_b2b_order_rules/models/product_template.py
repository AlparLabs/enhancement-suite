# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    b2b_order_limit_ids = fields.One2many(
        'b2b.product.order.limit',
        'product_tmpl_id',
        string="Límites B2B por Canal Web"
    )

    b2b_packaging_qty = fields.Float(
        string="Múltiplo de Empaque por Defecto",
        default=1.0,
        digits='Product Unit of Measure',
        help="Cantidad mínima y múltiplo requerido para pedidos (ej. 12 para caja de 12 u.). Si es 1, se permite venta por unidad suelta."
    )
    b2b_packaging_name = fields.Char(
        string="Nombre del Empaque",
        default="Unidad",
        help="Nombre de la presentación por defecto (ej. Caja x 12, Display x 24, Bulto x 72)."
    )

    def _get_b2b_order_limit_for_website(self, website, order_date=None):
        """
        Retorna la regla b2b.product.order.limit aplicable para el sitio web indicado,
        priorizando reglas específicas por temporada (fechas) o semana sobre la regla general.
        """
        self.ensure_one()
        if not website or not self.b2b_order_limit_ids:
            return self.env['b2b.product.order.limit']

        website_rules = self.b2b_order_limit_ids.filtered(lambda l: l.website_id == website)
        if not website_rules:
            return self.env['b2b.product.order.limit']

        target_date = order_date or fields.Date.context_today(self)
        current_week = target_date.isocalendar()[1]

        # Prioridad 1: Reglas con rango de fechas específico
        date_rules = website_rules.filtered(
            lambda r: r.date_from and r.date_to and r.date_from <= target_date <= r.date_to
        )
        if date_rules:
            return date_rules[0]

        # Prioridad 2: Reglas con número de semana específico
        week_rules = website_rules.filtered(
            lambda r: r.week_number and r.week_number == current_week
        )
        if week_rules:
            return week_rules[0]

        # Prioridad 3: Regla general permanente (sin fechas ni semana)
        default_rules = website_rules.filtered(
            lambda r: not r.date_from and not r.date_to and not r.week_number
        )
        if default_rules:
            return default_rules[0]

        return self.env['b2b.product.order.limit']

    def _get_b2b_packaging_info(self, website, order_date=None):
        """
        Retorna la tupla (packaging_qty, packaging_name) aplicable para este sitio web.
        Si la regla del canal especifica un múltiplo > 1, prevalece sobre el valor por defecto.
        """
        self.ensure_one()
        rule = self._get_b2b_order_limit_for_website(website, order_date=order_date)
        if rule and rule.packaging_qty > 1.0:
            pack_name = rule.packaging_name or self.b2b_packaging_name or f"Empaque x {int(rule.packaging_qty)}"
            return rule.packaging_qty, pack_name
        if self.b2b_packaging_qty > 1.0:
            pack_name = self.b2b_packaging_name or f"Empaque x {int(self.b2b_packaging_qty)}"
            return self.b2b_packaging_qty, pack_name
        return 1.0, self.b2b_packaging_name or "Unidad"


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_b2b_order_limit_for_website(self, website, order_date=None):
        self.ensure_one()
        return self.product_tmpl_id._get_b2b_order_limit_for_website(website, order_date=order_date)

    def _get_b2b_packaging_info(self, website, order_date=None):
        self.ensure_one()
        return self.product_tmpl_id._get_b2b_packaging_info(website, order_date=order_date)
