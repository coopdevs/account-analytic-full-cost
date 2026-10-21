# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.tools import SQL

from .analytic_plan import FULL_COST_ROLES


class AccountAnalyticFullCostReport(models.Model):
    """Full cost of the analytic lines as it would have been computed at the
    ``analysis_date`` given in the context (today by default).

    The multipliers are computed on the fly for that date, so nothing is
    stored and the analytic lines are left untouched."""

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

    @property
    def _table_query(self):
        analysis_date = self._get_analysis_date()
        plan_model = self.env["account.analytic.plan"]
        companies = self.env["res.company"].sudo().search([])
        windows = SQL(", ").join(
            SQL(
                "(%s, %s::date, %s::date, %s)",
                company.id,
                analysis_date,
                plan_model._get_full_cost_period_start(company, analysis_date),
                company.full_cost_weight_basis or "expenses",
            )
            for company in companies
        )
        return SQL(
            """
            WITH RECURSIVE
            company_dates (company_id, analysis_date, window_start, weight_basis)
                AS (VALUES %(windows)s),
            window_line AS (
                SELECT line.*
                FROM account_analytic_line line
                JOIN company_dates dates
                    ON line.company_id = dates.company_id
                    AND line.date >= dates.window_start
                    AND line.date <= dates.analysis_date
            ),
            plan_closure AS (
                SELECT plan.id AS ancestor_id, plan.id AS descendant_id
                FROM account_analytic_plan plan

                UNION ALL

                SELECT closure.ancestor_id, child.id AS descendant_id
                FROM plan_closure closure
                JOIN account_analytic_plan child
                    ON child.parent_id = closure.descendant_id
            ),
            excluded_plans AS (
                SELECT DISTINCT closure.descendant_id AS plan_id
                FROM plan_closure closure
                JOIN account_analytic_plan ancestor
                    ON ancestor.id = closure.ancestor_id
                WHERE ancestor.full_cost_role = 'not_analyzed'
            ),
            line_account AS (%(line_account)s),
            direct_weight AS (
                SELECT
                    line.company_id,
                    account.plan_id,
                    SUM(
                        CASE
                            WHEN dates.weight_basis = 'revenue'
                                AND line.amount > 0 THEN line.amount
                            WHEN dates.weight_basis != 'revenue'
                                AND line.amount < 0 THEN -line.amount
                            ELSE 0.0
                        END
                    ) AS weight
                FROM window_line line
                JOIN company_dates dates ON dates.company_id = line.company_id
                JOIN line_account ON line_account.line_id = line.id
                JOIN account_analytic_account account
                    ON account.id = line_account.account_id
                WHERE account.plan_id NOT IN (SELECT plan_id FROM excluded_plans)
                GROUP BY line.company_id, account.plan_id
            ),
            subtree_weight AS (
                SELECT
                    direct.company_id,
                    closure.ancestor_id AS plan_id,
                    SUM(direct.weight) AS weight
                FROM direct_weight direct
                JOIN plan_closure closure
                    ON closure.descendant_id = direct.plan_id
                GROUP BY direct.company_id, closure.ancestor_id
            ),
            isolated_rate AS (
                SELECT
                    dates.company_id,
                    plan.id AS plan_id,
                    plan.parent_id,
                    CASE
                        WHEN excluded.plan_id IS NOT NULL THEN 'not_analyzed'
                        ELSE plan.full_cost_role
                    END AS full_cost_role,
                    CASE
                        WHEN excluded.plan_id IS NOT NULL THEN 1.0
                        WHEN plan.full_cost_role = 'reproductive' THEN 0.0
                        WHEN productive.weight > 0.0 THEN
                            (productive.weight + reproductive.weight)
                            / productive.weight
                        ELSE 1.0
                    END AS isolated_multiplier
                FROM company_dates dates
                CROSS JOIN account_analytic_plan plan
                LEFT JOIN excluded_plans excluded ON excluded.plan_id = plan.id
                LEFT JOIN direct_weight direct
                    ON direct.company_id = dates.company_id
                    AND direct.plan_id = plan.id
                CROSS JOIN LATERAL (
                    SELECT
                        COALESCE(direct.weight, 0.0)
                        + COALESCE(SUM(child_weight.weight), 0.0) AS weight
                    FROM account_analytic_plan child
                    JOIN subtree_weight child_weight
                        ON child_weight.company_id = dates.company_id
                        AND child_weight.plan_id = child.id
                    WHERE child.parent_id = plan.id
                        AND child.full_cost_role = 'productive'
                        AND child.id NOT IN (SELECT plan_id FROM excluded_plans)
                ) productive
                CROSS JOIN LATERAL (
                    SELECT COALESCE(SUM(child_weight.weight), 0.0) AS weight
                    FROM account_analytic_plan child
                    JOIN subtree_weight child_weight
                        ON child_weight.company_id = dates.company_id
                        AND child_weight.plan_id = child.id
                    WHERE child.parent_id = plan.id
                        AND child.full_cost_role = 'reproductive'
                        AND child.id NOT IN (SELECT plan_id FROM excluded_plans)
                ) reproductive
            ),
            final_rate AS (
                SELECT
                    isolated.company_id,
                    isolated.plan_id,
                    isolated.full_cost_role,
                    isolated.isolated_multiplier AS full_cost_multiplier
                FROM isolated_rate isolated
                WHERE isolated.parent_id IS NULL

                UNION ALL

                SELECT
                    isolated.company_id,
                    isolated.plan_id,
                    isolated.full_cost_role,
                    isolated.isolated_multiplier * parent.full_cost_multiplier
                FROM isolated_rate isolated
                JOIN final_rate parent
                    ON parent.company_id = isolated.company_id
                    AND parent.plan_id = isolated.parent_id
            ),
            line_rate AS (
                SELECT
                    line.id AS line_id,
                    CASE
                        WHEN BOOL_OR(rate.full_cost_role = 'reproductive')
                            THEN 'reproductive'
                        WHEN COUNT(rate.plan_id) FILTER (
                            WHERE rate.full_cost_role != 'not_analyzed'
                        ) = 0 THEN 'not_analyzed'
                        ELSE 'productive'
                    END AS full_cost_role,
                    COALESCE(
                        EXP(
                            SUM(LN(rate.full_cost_multiplier)) FILTER (
                                WHERE rate.full_cost_role = 'productive'
                            )
                        ),
                        1.0
                    ) AS full_cost_multiplier
                FROM window_line line
                LEFT JOIN line_account ON line_account.line_id = line.id
                LEFT JOIN account_analytic_account account
                    ON account.id = line_account.account_id
                LEFT JOIN final_rate rate
                    ON rate.company_id = line.company_id
                    AND rate.plan_id = account.plan_id
                GROUP BY line.id
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
                CASE
                    WHEN line.amount > 0 THEN line.amount
                    WHEN rate.full_cost_role = 'reproductive' THEN 0.0
                    ELSE line.amount * rate.full_cost_multiplier
                END AS full_cost_amount,
                CASE
                    WHEN line.amount > 0 THEN 0.0
                    WHEN rate.full_cost_role = 'reproductive' THEN -line.amount
                    ELSE line.amount * (rate.full_cost_multiplier - 1.0)
                END AS full_cost_delta,
                rate.full_cost_role,
                CASE
                    WHEN line.amount > 0 THEN 1.0
                    WHEN rate.full_cost_role = 'reproductive' THEN 0.0
                    ELSE rate.full_cost_multiplier
                END AS full_cost_multiplier
            FROM window_line line
            JOIN company_dates dates ON dates.company_id = line.company_id
            JOIN line_rate rate ON rate.line_id = line.id
            """,
            windows=windows,
            line_account=self._get_line_account_query(),
        )
