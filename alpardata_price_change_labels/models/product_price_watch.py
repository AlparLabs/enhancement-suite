from __future__ import annotations

import logging
import threading

from odoo import _, api, fields, models
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

LABEL_REPORT = 'report.product_label_3x8.report_producttemplatelabel3x8'
BATCH_SIZE = 1000


class ProductPriceWatch(models.Model):
    _name = 'product.price.watch'
    _description = 'Control de precio de góndola'
    _order = 'label_pending desc, product_tmpl_id'
    _rec_name = 'product_tmpl_id'
    _check_company_auto = True

    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    categ_id = fields.Many2one(related='product_tmpl_id.categ_id', store=True, string='Categoría')
    shelf_price = fields.Monetary(string='Precio de góndola')
    shelf_price_untaxed = fields.Monetary(string='Precio sin impuestos')
    replacement_cost = fields.Monetary(string='Costo de reposición')
    target_markup_pct = fields.Float(
        related='product_tmpl_id.target_markup_pct', string='Recargo objetivo (%)',
    )
    markup_pct = fields.Float(
        string='Recargo actual (%)', compute='_compute_markup', store=True, digits=(16, 2),
    )
    markup_alert = fields.Selection(
        [('ok', 'OK'), ('below', 'Bajo objetivo'), ('no_cost', 'Sin costo')],
        string='Margen', compute='_compute_markup', store=True, index=True,
    )
    label_printed_price = fields.Monetary(string='Precio impreso')
    label_printed_date = fields.Datetime(string='Impresa el')
    label_variation_pct = fields.Float(
        string='Variación (%)', compute='_compute_label_pending', store=True, digits=(16, 2),
    )
    label_pending = fields.Boolean(
        string='Etiqueta pendiente', compute='_compute_label_pending', store=True, index=True,
    )
    refreshed_at = fields.Datetime(string='Actualizado')

    _product_company_uniq = models.Constraint(
        'UNIQUE(product_tmpl_id, company_id)',
        'Ya existe un control de precio para ese producto y empresa.',
    )

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('shelf_price_untaxed', 'replacement_cost',
                 'product_tmpl_id.target_markup_pct', 'company_id.markup_tolerance_pct')
    def _compute_markup(self) -> None:
        for rec in self:
            if not rec.replacement_cost:
                rec.markup_pct = 0.0
                rec.markup_alert = 'no_cost'
                continue
            rec.markup_pct = (rec.shelf_price_untaxed / rec.replacement_cost - 1) * 100
            floor = rec.target_markup_pct - rec.company_id.markup_tolerance_pct
            rec.markup_alert = 'below' if rec.markup_pct < floor else 'ok'

    @api.depends('shelf_price', 'label_printed_price')
    def _compute_label_pending(self) -> None:
        for rec in self:
            rec.label_pending = float_compare(
                rec.shelf_price, rec.label_printed_price, precision_digits=2,
            ) != 0
            rec.label_variation_pct = (
                (rec.shelf_price / rec.label_printed_price - 1) * 100
                if rec.label_printed_price else 0.0
            )

    # ── Refresco ──────────────────────────────────────────────────────────────
    @api.model
    def _label_price(self, template, company, pricelist):
        """(precio final, precio sin impuestos) tal como los imprime la etiqueta 3x8."""
        report = self.env[LABEL_REPORT].with_company(company)
        info = report._get_label_info(template.with_company(company), pricelist=pricelist or None)
        return info['price_final'], info['price_net']

    @api.model
    def _refresh(self, templates, company):
        """Crea o actualiza las filas de `templates` para `company`. Devuelve las filas."""
        self = self.sudo()
        existing = self.search([
            ('product_tmpl_id', 'in', templates.ids), ('company_id', '=', company.id),
        ])
        by_template = {rec.product_tmpl_id.id: rec for rec in existing}
        pricelist = company.shelf_pricelist_id
        now = fields.Datetime.now()
        to_create = []
        for template in templates:
            price, untaxed = self._label_price(template, company, pricelist)
            vals = {
                'shelf_price': price,
                'shelf_price_untaxed': untaxed,
                'replacement_cost': template.with_company(company).replacement_cost,
                'refreshed_at': now,
            }
            rec = by_template.get(template.id)
            if rec:
                rec.write(vals)
            else:
                to_create.append({
                    **vals,
                    'product_tmpl_id': template.id,
                    'company_id': company.id,
                    'label_printed_price': 0.0,
                })
        created = self.create(to_create) if to_create else self.browse()
        return existing | created

    @api.model
    def _templates_for_company(self, company):
        return self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('company_id', 'in', [company.id, False]),
        ])

    @api.model
    def _refresh_company(self, company):
        templates = self._templates_for_company(company)
        result = self.browse()
        testing = getattr(threading.current_thread(), 'testing', False)
        for start in range(0, len(templates), BATCH_SIZE):
            result |= self._refresh(templates[start:start + BATCH_SIZE], company)
            if not testing:
                self.env.cr.commit()
        return result

    @api.model
    def _cron_refresh(self) -> None:
        for company in self.env['res.company'].search([]):
            _logger.info('Control de precios de góndola: empresa %s', company.name)
            self._refresh_company(company)

    def action_refresh(self) -> None:
        for company in self.company_id:
            recs = self.filtered(lambda r: r.company_id == company)
            self._refresh(recs.product_tmpl_id, company)

    # ── Impresión ─────────────────────────────────────────────────────────────
    @api.model
    def _mark_printed(self, templates, company, pricelist):
        """Registra el precio impreso con `pricelist` (la del wizard)."""
        watches = self._refresh(templates, company)
        now = fields.Datetime.now()
        for rec in watches:
            price, _untaxed = self._label_price(rec.product_tmpl_id, company, pricelist)
            rec.write({'label_printed_price': price, 'label_printed_date': now})
        return watches

    def action_print_labels(self) -> dict:
        company = self.company_id[:1] or self.env.company
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imprimir etiquetas'),
            'res_model': 'product.label.layout',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_product_tmpl_ids': self.product_tmpl_id.ids,
                'default_print_format': '3x8xprice',
                'default_pricelist_id': company.shelf_pricelist_id.id,
            },
        }
