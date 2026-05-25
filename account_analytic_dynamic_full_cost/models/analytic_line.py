from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    full_cost_role = fields.Selection(
        [
            ("productive", "Productive"),
            ("reproductive", "Reproductive"),
            ("not_analyzed", "Not Analyzed"),
        ],
        compute="_compute_full_cost_role",
        string="Full Cost Role",
        store=True,
        readonly=True,
    )

    full_cost_amount = fields.Float(
        string="Full Cost Amount",
        help=(
            "Amount after applying the analytic plan full cost multiplier."
        ),
    )
    full_cost_multiplier_snapshot = fields.Float(
        string="Full Cost Multiplier",
        readonly=True,
        copy=False,
    )
    is_in_full_cost_window = fields.Boolean(
        string="Inside Full-Cost Window",
        compute="_compute_is_in_full_cost_window",
        search="_search_is_in_full_cost_window",
    )

    def _get_current_full_cost_window_domain(self):
        company = self.env.company
        date_to = fields.Date.context_today(self)
        date_from = self.env["account.analytic.plan"]._get_full_cost_period_start(
            company,
            date_to,
        )
        return [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]

    def _compute_is_in_full_cost_window(self):
        date_to = fields.Date.context_today(self)
        date_from_by_company = {}
        plan_model = self.env["account.analytic.plan"]
        for line in self:
            company = line.company_id or self.env.company
            if company.id not in date_from_by_company:
                date_from_by_company[company.id] = (
                    plan_model._get_full_cost_period_start(company, date_to)
                )
            line.is_in_full_cost_window = bool(
                line.date
                and line.company_id
                and line.date >= date_from_by_company[company.id]
                and line.date <= date_to
            )

    def _search_is_in_full_cost_window(self, operator, value):
        if operator not in ("=", "!="):
            return []
        positive = (operator == "=" and value) or (operator == "!=" and not value)
        domain = self._get_current_full_cost_window_domain()
        if positive:
            return domain
        company = self.env.company
        date_to = fields.Date.context_today(self)
        date_from = self.env["account.analytic.plan"]._get_full_cost_period_start(
            company,
            date_to,
        )
        return [
            "|",
            "|",
            ("company_id", "!=", company.id),
            ("date", "<", date_from),
            ("date", ">", date_to),
        ]

    def recompute_full_cost_amount(self):
        for line in self:
            line._compute_full_cost_amount()

    @api.depends("account_id")
    def _compute_full_cost_role(self):
        for line in self:
            line.full_cost_role = line._get_full_cost_role()

    def _get_full_cost_accounts(self):
        self.ensure_one()
        if hasattr(self, "_get_analytic_accounts"):
            return self._get_analytic_accounts()
        return self.account_id

    def _get_included_full_cost_plans(self):
        self.ensure_one()
        return self._get_full_cost_accounts().mapped("plan_id").filtered(
            lambda plan: not plan._is_excluded_from_full_cost()
        )

    def _get_full_cost_role(self):
        self.ensure_one()
        plans = self._get_included_full_cost_plans()
        if not plans:
            return "not_analyzed"
        if any(plan.full_cost_role == "reproductive" for plan in plans):
            return "reproductive"
        return "productive"

    def _compute_full_cost_amount(self):
        self.ensure_one()

        base_amount = self.amount or 0.0
        values = {
            "full_cost_amount": base_amount,
            "full_cost_multiplier_snapshot": 1.0,
        }

        if base_amount > 0:
            self.update(values)
            return

        if not self.company_id:
            self.update(values)
            return

        plans = self._get_included_full_cost_plans()
        if not plans:
            self.update(values)
            return

        if any(plan.full_cost_role == "reproductive" for plan in plans):
            values.update(
                {
                    "full_cost_amount": 0.0,
                    "full_cost_multiplier_snapshot": 0.0,
                }
            )
            self.update(values)
            return

        multiplier = 1.0
        for plan in plans:
            multiplier *= plan.full_cost_multiplier
        values.update(
            {
                "full_cost_amount": base_amount * multiplier,
                "full_cost_multiplier_snapshot": multiplier,
            }
        )
        self.update(values)
