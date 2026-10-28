# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.tools import SQL

from .analytic_plan import FULL_COST_ROLES


class AccountAnalyticFullCostReport(models.Model):
    """Full cost of the analytic lines as it would have been computed at the
    ``analysis_date`` given in the context (today by default).

    The multipliers are computed on the fly for that date, with the same
    algorithm as the stored ones, so nothing is stored and the analytic lines
    are left untouched."""

    _name = "account.analytic.full.cost.report"
    _description = "Historical Full Cost Analysis"
    _auto = False
    _order = "date desc, id desc"
    _depends = {
        "account.analytic.line": ["amount", "date", "company_id", "account_id"],
        "account.analytic.account": ["plan_id"],
        "account.analytic.plan": ["parent_id", "full_cost_role"],
        "res.company": [
            "full_cost_period",
            "full_cost_weight_basis",
            "full_cost_window_days",
        ],
    }

    line_id = fields.Many2one("account.analytic.line", readonly=True)
    analysis_date = fields.Date(readonly=True)
    window_start = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    date = fields.Date(readonly=True)
    account_id = fields.Many2one("account.analytic.account", readonly=True)
    amount = fields.Monetary(readonly=True)
    full_cost_amount = fields.Monetary(readonly=True)
    full_cost_delta = fields.Monetary(readonly=True)
    full_cost_role = fields.Selection(FULL_COST_ROLES, readonly=True)
    full_cost_multiplier = fields.Float(readonly=True)

    def _get_analysis_date(self):
        return fields.Date.to_date(
            self.env.context.get("full_cost_analysis_date")
        ) or fields.Date.context_today(self)

    def _get_line_account_query(self):
        """One row per (analytic line, analytic account) for every plan
        column of the analytic lines."""
        line_model = self.env["account.analytic.line"]
        fnames = line_model._get_plan_fnames()
        # Plan columns are created dynamically, so they are not in _depends
        line_model.flush_model(fnames)
        return SQL(" UNION ALL ").join(
            SQL(
                "SELECT id AS line_id, %(col)s AS account_id "
                "FROM account_analytic_line WHERE %(col)s IS NOT NULL",
                col=SQL.identifier(fname),
            )
            for fname in fnames
        )

    def _get_plan_rates_query(self, companies, analysis_date):
        """VALUES of (company, plan, role, multiplier) as computed on the
        analysis date, for every company and plan."""
        plan_model = self.env["account.analytic.plan"].sudo()
        plans = plan_model.search([])
        roles = {
            plan.id: "not_analyzed"
            if plan._is_excluded_from_full_cost()
            else plan.full_cost_role
            for plan in plans
        }
        rows = [
            SQL("(%s, %s, %s, %s::float)", company.id, plan_id, roles[plan_id], value)
            for company in companies
            for plan_id, value in plan_model._compute_full_cost_multipliers(
                company, analysis_date
            ).items()
        ]
        if not rows:
            return SQL(
                "SELECT NULL::int, NULL::int, NULL::varchar, NULL::float LIMIT 0"
            )
        return SQL("VALUES %s", SQL(", ").join(rows))

    def _get_readable_lines_condition(self):
        """Only show the analytic lines the user can read: the report is a
        SQL view, so the record rules of the analytic lines would not apply.
        The multipliers are still computed with all the lines."""
        if self.env.su:
            return SQL("TRUE")
        readable = self.env["account.analytic.line"]._search([])
        return SQL("line.id IN %s", readable.subselect())

    @property
    def _table_query(self):
        analysis_date = self._get_analysis_date()
        plan_model = self.env["account.analytic.plan"]
        companies = self.env["res.company"].sudo().search([])
        windows = SQL(", ").join(
            SQL(
                "(%s, %s::date, %s::date, %s, %s)",
                company.id,
                analysis_date,
                plan_model._get_full_cost_period_start(company, analysis_date),
                company.full_cost_weight_basis or "expenses",
                company.currency_id.decimal_places,
            )
            for company in companies
        )
        return SQL(
            """
            WITH
            company_dates (
                company_id, analysis_date, window_start, weight_basis, digits
            ) AS (VALUES %(windows)s),
            plan_rate (company_id, plan_id, full_cost_role, full_cost_multiplier)
                AS (%(plan_rates)s),
            window_line AS (
                SELECT line.*
                FROM account_analytic_line line
                JOIN company_dates dates
                    ON line.company_id = dates.company_id
                    AND line.date >= dates.window_start
                    AND line.date <= dates.analysis_date
                WHERE %(readable_lines)s
            ),
            line_account AS (%(line_account)s),
            line_rate AS (
                SELECT
                    line.id AS line_id,
                    CASE
                        WHEN BOOL_OR(rate.full_cost_role = 'reproductive')
                            THEN 'reproductive'
                        WHEN COUNT(rate.plan_id) FILTER (
                            WHERE rate.full_cost_role = 'productive'
                        ) = 0 THEN 'not_analyzed'
                        ELSE 'productive'
                    END AS full_cost_role,
                    -- Product of the multipliers of the productive plans
                    COALESCE(
                        EXP(
                            SUM(LN(ABS(rate.full_cost_multiplier))) FILTER (
                                WHERE rate.full_cost_role = 'productive'
                                    AND rate.full_cost_multiplier != 0.0
                            )
                        ),
                        1.0
                    )
                    * CASE
                        WHEN BOOL_OR(
                            rate.full_cost_role = 'productive'
                            AND rate.full_cost_multiplier = 0.0
                        ) THEN 0.0
                        WHEN MOD(
                            COUNT(rate.plan_id) FILTER (
                                WHERE rate.full_cost_role = 'productive'
                                    AND rate.full_cost_multiplier < 0.0
                            ),
                            2
                        ) = 1 THEN -1.0
                        ELSE 1.0
                    END AS full_cost_multiplier
                FROM window_line line
                LEFT JOIN line_account ON line_account.line_id = line.id
                LEFT JOIN account_analytic_account account
                    ON account.id = line_account.account_id
                LEFT JOIN plan_rate rate
                    ON rate.company_id = line.company_id
                    AND rate.plan_id = account.plan_id
                GROUP BY line.id
            ),
            line_value AS (
                SELECT
                    line.id AS line_id,
                    CASE
                        WHEN rate.full_cost_role = 'reproductive' THEN 0.0
                        WHEN rate.full_cost_role = 'productive'
                            AND (
                                (dates.weight_basis = 'revenue' AND line.amount > 0)
                                OR (dates.weight_basis != 'revenue' AND line.amount < 0)
                            )
                            THEN rate.full_cost_multiplier
                        ELSE 1.0
                    END AS full_cost_multiplier
                FROM window_line line
                JOIN company_dates dates ON dates.company_id = line.company_id
                JOIN line_rate rate ON rate.line_id = line.id
            )
            SELECT
                line.id AS id,
                line.id AS line_id,
                dates.analysis_date,
                dates.window_start,
                line.company_id,
                line.date,
                line.account_id,
                line.amount,
                -- Rounded as the stored full cost amount of the lines
                ROUND(
                    line.amount * value.full_cost_multiplier::numeric, dates.digits
                ) AS full_cost_amount,
                ROUND(
                    line.amount * value.full_cost_multiplier::numeric, dates.digits
                ) - line.amount AS full_cost_delta,
                rate.full_cost_role,
                value.full_cost_multiplier
            FROM window_line line
            JOIN company_dates dates ON dates.company_id = line.company_id
            JOIN line_rate rate ON rate.line_id = line.id
            JOIN line_value value ON value.line_id = line.id
            """,
            windows=windows,
            plan_rates=self._get_plan_rates_query(companies, analysis_date),
            readable_lines=self._get_readable_lines_condition(),
            line_account=self._get_line_account_query(),
        )
