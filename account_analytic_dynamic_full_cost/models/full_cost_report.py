from odoo import fields, models, tools


class AccountAnalyticFullCostReport(models.Model):
    _name = "account.analytic.full.cost.report"
    _description = "Historical Full Cost Analysis"
    _auto = False
    _order = "date desc, id desc"

    line_id = fields.Many2one("account.analytic.line", readonly=True)
    analysis_date = fields.Date(readonly=True)
    window_start = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    date = fields.Date(readonly=True)
    account_id = fields.Many2one("account.analytic.account", readonly=True)
    amount = fields.Float(readonly=True)
    full_cost_amount = fields.Float(readonly=True)
    full_cost_delta = fields.Float(readonly=True)
    full_cost_role = fields.Selection(
        [
            ("productive", "Productive"),
            ("reproductive", "Reproductive"),
            ("not_analyzed", "Not Analyzed"),
        ],
        readonly=True,
    )
    full_cost_multiplier = fields.Float(readonly=True)

    def _ensure_sql_columns(self):
        self.env.cr.execute(
            """
            ALTER TABLE res_company
                ADD COLUMN IF NOT EXISTS full_cost_period varchar,
                ADD COLUMN IF NOT EXISTS full_cost_weight_basis varchar,
                ADD COLUMN IF NOT EXISTS full_cost_window_days integer
            """
        )
        self.env.cr.execute(
            """
            ALTER TABLE account_analytic_plan
                ADD COLUMN IF NOT EXISTS full_cost_role varchar
            """
        )
        self.env.cr.execute(
            """
            ALTER TABLE account_analytic_line
                ADD COLUMN IF NOT EXISTS full_cost_role varchar
            """
        )

    def init(self):
        self._ensure_sql_columns()
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW account_analytic_full_cost_report AS (
                WITH RECURSIVE
                company_dates AS (
                    SELECT
                        company.id AS company_id,
                        day::date AS analysis_date,
                        CASE COALESCE(company.full_cost_period, 'biannual')
                            WHEN 'annual' THEN (day - INTERVAL '1 year')::date
                            WHEN 'biannual' THEN (day - INTERVAL '2 years')::date
                            WHEN 'triannual' THEN (day - INTERVAL '3 years')::date
                            WHEN 'monthly' THEN (day - INTERVAL '1 month')::date
                            ELSE (
                                day
                                - (
                                    GREATEST(
                                        COALESCE(company.full_cost_window_days, 30),
                                        1
                                    ) - 1
                                ) * INTERVAL '1 day'
                            )::date
                        END AS window_start,
                        COALESCE(company.full_cost_weight_basis, 'expenses')
                            AS weight_basis
                    FROM res_company company
                    JOIN LATERAL generate_series(
                        COALESCE(
                            (
                                SELECT MIN(line.date)
                                FROM account_analytic_line line
                                WHERE line.company_id = company.id
                            ),
                            CURRENT_DATE
                        ),
                        CURRENT_DATE,
                        INTERVAL '1 day'
                    ) AS series(day) ON TRUE
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
                    SELECT descendant_id AS plan_id
                    FROM plan_closure closure
                    JOIN account_analytic_plan ancestor
                        ON ancestor.id = closure.ancestor_id
                    WHERE COALESCE(ancestor.full_cost_role, 'productive')
                        = 'not_analyzed'
                ),
                line_account AS (
                    SELECT DISTINCT
                        line.id AS line_id,
                        (entry.value #>> '{}')::integer AS account_id
                    FROM account_analytic_line line
                    CROSS JOIN LATERAL jsonb_each(to_jsonb(line))
                        AS entry(key, value)
                    WHERE (
                            entry.key = 'account_id'
                            OR entry.key ~ '^x_plan[0-9]+_id$'
                        )
                        AND entry.value != 'null'::jsonb

                    UNION

                    SELECT DISTINCT
                        line.id AS line_id,
                        split.account_id::integer AS account_id
                    FROM account_analytic_line line
                    CROSS JOIN LATERAL jsonb_each(
                        COALESCE(
                            to_jsonb(line)->'analytic_distribution',
                            '{}'::jsonb
                        )
                    ) AS distribution(key, percentage)
                    CROSS JOIN LATERAL regexp_split_to_table(
                        distribution.key,
                        ','
                    ) AS split(account_id)
                    WHERE split.account_id != ''
                ),
                direct_weight AS (
                    SELECT
                        dates.company_id,
                        dates.analysis_date,
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
                    FROM company_dates dates
                    JOIN account_analytic_line line
                        ON line.company_id = dates.company_id
                        AND line.date >= dates.window_start
                        AND line.date <= dates.analysis_date
                    JOIN line_account line_account
                        ON line_account.line_id = line.id
                    JOIN account_analytic_account account
                        ON account.id = line_account.account_id
                    LEFT JOIN excluded_plans excluded
                        ON excluded.plan_id = account.plan_id
                    WHERE excluded.plan_id IS NULL
                    GROUP BY dates.company_id, dates.analysis_date, account.plan_id
                ),
                subtree_weight AS (
                    SELECT
                        direct.company_id,
                        direct.analysis_date,
                        closure.ancestor_id AS plan_id,
                        SUM(direct.weight) AS weight
                    FROM direct_weight direct
                    JOIN plan_closure closure
                        ON closure.descendant_id = direct.plan_id
                    GROUP BY
                        direct.company_id,
                        direct.analysis_date,
                        closure.ancestor_id
                ),
                plan_dates AS (
                    SELECT
                        dates.company_id,
                        dates.analysis_date,
                        plan.id AS plan_id,
                        plan.parent_id,
                        COALESCE(plan.full_cost_role, 'productive')
                            AS full_cost_role
                    FROM company_dates dates
                    CROSS JOIN account_analytic_plan plan
                ),
                isolated_rate AS (
                    SELECT
                        plan_dates.company_id,
                        plan_dates.analysis_date,
                        plan_dates.plan_id,
                        plan_dates.parent_id,
                        CASE
                            WHEN excluded.plan_id IS NOT NULL THEN 'not_analyzed'
                            ELSE plan_dates.full_cost_role
                        END AS full_cost_role,
                        CASE
                            WHEN excluded.plan_id IS NOT NULL THEN 1.0
                            WHEN plan_dates.full_cost_role = 'reproductive' THEN 0.0
                            WHEN productive.weight > 0.0 THEN (
                                productive.weight
                                + COALESCE(reproductive.weight, 0.0)
                            ) / productive.weight
                            ELSE 1.0
                        END AS isolated_multiplier
                    FROM plan_dates
                    LEFT JOIN excluded_plans excluded
                        ON excluded.plan_id = plan_dates.plan_id
                    LEFT JOIN LATERAL (
                        SELECT
                            COALESCE(
                                CASE
                                    WHEN plan_dates.full_cost_role = 'productive'
                                        THEN (
                                            SELECT direct.weight
                                            FROM direct_weight direct
                                            WHERE direct.company_id =
                                                plan_dates.company_id
                                                AND direct.analysis_date =
                                                    plan_dates.analysis_date
                                                AND direct.plan_id =
                                                    plan_dates.plan_id
                                        )
                                    ELSE 0.0
                                END,
                                0.0
                            )
                            + COALESCE(
                                (
                                    SELECT SUM(child_weight.weight)
                                    FROM account_analytic_plan child
                                    LEFT JOIN excluded_plans child_excluded
                                        ON child_excluded.plan_id = child.id
                                    LEFT JOIN subtree_weight child_weight
                                        ON child_weight.company_id =
                                            plan_dates.company_id
                                        AND child_weight.analysis_date =
                                            plan_dates.analysis_date
                                        AND child_weight.plan_id = child.id
                                    WHERE child.parent_id = plan_dates.plan_id
                            AND COALESCE(child.full_cost_role, 'productive')
                                = 'productive'
                                        AND child_excluded.plan_id IS NULL
                                ),
                                0.0
                            ) AS weight
                    ) productive ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT COALESCE(SUM(child_weight.weight), 0.0) AS weight
                        FROM account_analytic_plan child
                        LEFT JOIN excluded_plans child_excluded
                            ON child_excluded.plan_id = child.id
                        LEFT JOIN subtree_weight child_weight
                            ON child_weight.company_id = plan_dates.company_id
                            AND child_weight.analysis_date =
                                plan_dates.analysis_date
                            AND child_weight.plan_id = child.id
                        WHERE child.parent_id = plan_dates.plan_id
                            AND COALESCE(child.full_cost_role, 'productive')
                                = 'reproductive'
                            AND child_excluded.plan_id IS NULL
                    ) reproductive ON TRUE
                ),
                final_rate AS (
                    SELECT
                        isolated.company_id,
                        isolated.analysis_date,
                        isolated.plan_id,
                        isolated.parent_id,
                        isolated.full_cost_role,
                        isolated.isolated_multiplier AS full_cost_multiplier
                    FROM isolated_rate isolated
                    WHERE isolated.parent_id IS NULL

                    UNION ALL

                    SELECT
                        isolated.company_id,
                        isolated.analysis_date,
                        isolated.plan_id,
                        isolated.parent_id,
                        isolated.full_cost_role,
                        isolated.isolated_multiplier
                            * parent.full_cost_multiplier
                            AS full_cost_multiplier
                    FROM isolated_rate isolated
                    JOIN final_rate parent
                        ON parent.company_id = isolated.company_id
                        AND parent.analysis_date = isolated.analysis_date
                        AND parent.plan_id = isolated.parent_id
                ),
                line_rate AS (
                    SELECT
                        dates.company_id,
                        dates.analysis_date,
                        line.id AS line_id,
                        CASE
                            WHEN BOOL_OR(rate.full_cost_role = 'reproductive')
                                THEN 'reproductive'
                            WHEN COUNT(rate.plan_id) = 0 THEN 'not_analyzed'
                            ELSE 'productive'
                        END AS full_cost_role,
                        COALESCE(
                            EXP(
                                SUM(
                                    LN(NULLIF(rate.full_cost_multiplier, 0.0))
                                ) FILTER (
                                    WHERE rate.full_cost_role != 'reproductive'
                                )
                            ),
                            1.0
                        ) AS full_cost_multiplier
                    FROM company_dates dates
                    JOIN account_analytic_line line
                        ON line.company_id = dates.company_id
                        AND line.date >= dates.window_start
                        AND line.date <= dates.analysis_date
                    LEFT JOIN line_account line_account
                        ON line_account.line_id = line.id
                    LEFT JOIN account_analytic_account account
                        ON account.id = line_account.account_id
                    LEFT JOIN excluded_plans excluded
                        ON excluded.plan_id = account.plan_id
                    LEFT JOIN final_rate rate
                        ON rate.company_id = dates.company_id
                        AND rate.analysis_date = dates.analysis_date
                        AND rate.plan_id = account.plan_id
                        AND excluded.plan_id IS NULL
                    GROUP BY dates.company_id, dates.analysis_date, line.id
                )
                SELECT
                    row_number() OVER () AS id,
                    line.id AS line_id,
                    dates.analysis_date AS analysis_date,
                    dates.window_start AS window_start,
                    line.company_id AS company_id,
                    line.date AS date,
                    line.account_id AS account_id,
                    line.amount AS amount,
                    CASE
                        WHEN line.amount > 0 THEN line.amount
                        WHEN COALESCE(rate.full_cost_role, line.full_cost_role)
                            = 'reproductive' THEN 0.0
                        ELSE line.amount * COALESCE(rate.full_cost_multiplier, 1.0)
                    END AS full_cost_amount,
                    CASE
                        WHEN line.amount > 0 THEN 0.0
                        WHEN COALESCE(rate.full_cost_role, line.full_cost_role)
                            = 'reproductive' THEN -line.amount
                        ELSE line.amount * COALESCE(rate.full_cost_multiplier, 1.0)
                            - line.amount
                    END AS full_cost_delta,
                    COALESCE(
                        rate.full_cost_role,
                        line.full_cost_role,
                        'not_analyzed'
                    ) AS full_cost_role,
                    CASE
                        WHEN line.amount > 0 THEN 1.0
                        WHEN COALESCE(rate.full_cost_role, line.full_cost_role)
                            = 'reproductive' THEN 0.0
                        ELSE COALESCE(rate.full_cost_multiplier, 1.0)
                    END AS full_cost_multiplier
                FROM company_dates dates
                JOIN account_analytic_line line
                    ON line.company_id = dates.company_id
                    AND line.date >= dates.window_start
                    AND line.date <= dates.analysis_date
                LEFT JOIN line_rate rate
                    ON rate.company_id = dates.company_id
                    AND rate.analysis_date = dates.analysis_date
                    AND rate.line_id = line.id
            )
            """
        )
