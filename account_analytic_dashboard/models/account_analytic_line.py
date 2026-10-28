from odoo import api, fields, models
from odoo.osv import expression


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    amount_revenue = fields.Monetary(
        string="Revenue",
        currency_field="currency_id",
        compute="_compute_amount_revenue_expense",
        store=True,
        help="Amount of the line when it is positive.",
    )
    amount_expense = fields.Monetary(
        string="Expenses",
        currency_field="currency_id",
        compute="_compute_amount_revenue_expense",
        store=True,
        help="Amount of the line when it is negative (kept negative, so that "
        "revenue plus expenses is the amount).",
    )

    analytic_report_included = fields.Boolean(
        string="Included in Analytic Reports",
        compute="_compute_analytic_report_included",
        search="_search_analytic_report_included",
        help="Whether the line counts in the analytic reports, according to the "
        "personnel cost source of its company.",
    )

    @api.model
    def _get_analytic_report_domain(self, company):
        """Domain of the lines of the company counted by the analytic reports."""
        source = company.analytic_report_personnel_cost or "accounting"
        if source == "accounting":
            return [("general_account_id", "!=", False)]
        if source == "timesheets":
            return [
                (
                    "general_account_id",
                    "not in",
                    company.analytic_report_personnel_account_ids.ids,
                )
            ]
        return []

    @api.depends(
        "general_account_id",
        "company_id.analytic_report_personnel_cost",
        "company_id.analytic_report_personnel_account_ids",
    )
    def _compute_analytic_report_included(self):
        for line in self:
            domain = self._get_analytic_report_domain(line.company_id)
            line.analytic_report_included = bool(line.filtered_domain(domain))

    def _search_analytic_report_included(self, operator, value):
        if operator not in ("=", "!="):
            raise NotImplementedError(
                self.env._("Unsupported operator %s", operator)
            )
        domain = expression.OR(
            [
                expression.AND(
                    [
                        [("company_id", "=", company.id)],
                        self._get_analytic_report_domain(company),
                    ]
                )
                for company in self.env["res.company"].sudo().search([])
            ]
        )
        positive = (operator == "=") == bool(value)
        return domain if positive else ["!", *domain]

    @api.depends("amount")
    def _compute_amount_revenue_expense(self):
        for line in self:
            line.amount_revenue = max(line.amount, 0.0)
            line.amount_expense = min(line.amount, 0.0)
