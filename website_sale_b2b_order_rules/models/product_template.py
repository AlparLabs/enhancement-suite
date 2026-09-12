# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    b2b_order_limit_ids = fields.One2many(
        'b2b.product.order.limit',
        'product_tmpl_id',
        string="Límites B2B por Canal Web"
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


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_b2b_order_limit_for_website(self, website, order_date=None):
        self.ensure_one()
        return self.product_tmpl_id._get_b2b_order_limit_for_website(website, order_date=order_date)
