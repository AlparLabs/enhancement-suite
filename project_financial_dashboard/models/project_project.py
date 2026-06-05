from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Lets managers choose the currency in which the project financials are
    # expressed (e.g. USD for Argentine projects while company currency is ARS).
    project_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Project Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
        tracking=True,
        help='Currency used to display all financial indicators for this project. '
             'Amounts in other currencies are converted at the current exchange rate.',
    )

    # Override the native read-only currency_id so the entire profitability
    # panel (get_panel_data / _get_profitability_items) uses the project currency
    # instead of the company currency.  All existing conversion logic in
    # project_account, sale_project, project_purchase etc. calls
    # currency._convert(..., to_currency=self.currency_id) — by making
    # currency_id follow project_currency_id we get the correct output for free.
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_currency_id',
        string='Currency',
        readonly=True,
        export_string_translation=False,
    )

    @api.depends('project_currency_id', 'company_id')
    def _compute_currency_id(self):
        default = self.env.company.currency_id
        for project in self:
            project.currency_id = (
                project.project_currency_id
                or project.company_id.currency_id
                or default
            )

    amount_invoiced = fields.Monetary(
        string='Invoiced',
        currency_field='project_currency_id',
        compute='_compute_financial_totals',
        help='Total customer invoices posted (net of credit notes) in the project currency.',
    )
    amount_sold = fields.Monetary(
        string='Sales Orders',
        currency_field='project_currency_id',
        compute='_compute_financial_totals',
        help='Total confirmed/done sale order lines linked to this project analytic account.',
    )
    amount_purchased = fields.Monetary(
        string='Purchase Orders',
        currency_field='project_currency_id',
        compute='_compute_financial_totals',
        help='Total confirmed/done purchase order lines linked to this project analytic account.',
    )
    amount_margin = fields.Monetary(
        string='Gross Margin',
        currency_field='project_currency_id',
        compute='_compute_amount_margin',
        help='Sales Orders minus Purchase Orders in the project currency.',
    )

    @api.depends('account_id', 'project_currency_id', 'company_id')
    def _compute_financial_totals(self):
        """
        Compute invoiced, sold and purchased totals in the project's own currency.

        Uses the analytic distribution JSON field to link document lines to this
        project's analytic account, then converts each transaction to the project
        currency using the rate at the date of the transaction.
        """
        for project in self:
            if not project.account_id:
                project.amount_invoiced = 0.0
                project.amount_sold = 0.0
                project.amount_purchased = 0.0
                continue

            analytic_id = str(project.account_id.id)
            currency = project.project_currency_id
            company = project.company_id or self.env.company

            project.amount_invoiced = self._compute_amount_invoiced(
                analytic_id, currency, company
            )
            project.amount_sold = self._compute_amount_sold(
                analytic_id, currency, company
            )
            project.amount_purchased = self._compute_amount_purchased(
                analytic_id, currency, company
            )

    @api.depends('amount_sold', 'amount_purchased')
    def _compute_amount_margin(self):
        for project in self:
            project.amount_margin = project.amount_sold - project.amount_purchased

    def _compute_amount_invoiced(self, analytic_id, currency, company):
        """Sum posted customer invoices and credit notes linked to the analytic account."""
        self.env.cr.execute(
            """
            SELECT
                am.currency_id,
                am.move_type,
                SUM(am.amount_untaxed) AS amount
            FROM account_move am
            WHERE am.state = 'posted'
              AND am.move_type IN ('out_invoice', 'out_refund')
              AND am.company_id = %s
              AND EXISTS (
                  SELECT 1
                  FROM account_move_line aml
                  WHERE aml.move_id = am.id
                    AND (aml.analytic_distribution)::jsonb ? %s
              )
            GROUP BY am.currency_id, am.move_type
            """,
            [company.id, analytic_id],
        )
        total = 0.0
        for row in self.env.cr.dictfetchall():
            amount = self._convert_to_project_currency(
                row['amount'] or 0.0,
                row['currency_id'],
                currency,
                company,
            )
            total += amount if row['move_type'] == 'out_invoice' else -amount
        return total

    def _compute_amount_sold(self, analytic_id, currency, company):
        """Sum confirmed/done sale order lines linked to the analytic account."""
        self.env.cr.execute(
            """
            SELECT
                so.currency_id,
                SUM(sol.price_subtotal) AS amount
            FROM sale_order_line sol
            JOIN sale_order so ON sol.order_id = so.id
            WHERE so.state IN ('sale', 'done')
              AND so.company_id = %s
              AND (sol.analytic_distribution)::jsonb ? %s
            GROUP BY so.currency_id
            """,
            [company.id, analytic_id],
        )
        return self._sum_rows(currency, company)

    def _compute_amount_purchased(self, analytic_id, currency, company):
        """Sum confirmed/done purchase order lines linked to the analytic account."""
        self.env.cr.execute(
            """
            SELECT
                po.currency_id,
                SUM(pol.price_subtotal) AS amount
            FROM purchase_order_line pol
            JOIN purchase_order po ON pol.order_id = po.id
            WHERE po.state IN ('purchase', 'done')
              AND po.company_id = %s
              AND (pol.analytic_distribution)::jsonb ? %s
            GROUP BY po.currency_id
            """,
            [company.id, analytic_id],
        )
        return self._sum_rows(currency, company)

    def _sum_rows(self, currency, company):
        """Convert and sum a resultset of (currency_id, amount) rows."""
        total = 0.0
        for row in self.env.cr.dictfetchall():
            total += self._convert_to_project_currency(
                row['amount'] or 0.0,
                row['currency_id'],
                currency,
                company,
            )
        return total

    def _convert_to_project_currency(self, amount, from_currency_id, to_currency, company):
        """Convert *amount* from *from_currency_id* to *to_currency* at today's rate."""
        from_currency = self.env['res.currency'].browse(from_currency_id)
        if from_currency == to_currency:
            return amount
        return from_currency._convert(
            amount,
            to_currency,
            company,
            fields.Date.today(),
        )
