# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict
from datetime import timedelta
from functools import cache

from odoo import api, fields, models
from odoo.exceptions import ValidationError

FULL_COST_ROLES = [
    ("productive", "Productive"),
    ("reproductive", "Reproductive"),
    ("not_analyzed", "Not Analyzed"),
]


class AccountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    full_cost_role = fields.Selection(
        FULL_COST_ROLES,
        string="Full Cost Role",
        default="productive",
        required=True,
        help=(
            "Productive plans correspond to value-generating activity.\n"
            "Reproductive plans correspond to indirect costs to be spread "
            "over productive activity.\n"
            "Not analyzed plans and their descendants are excluded from "
            "full-cost calculations."
        ),
    )
    full_cost_multiplier = fields.Float(
        string="Full Cost Multiplier",
        company_dependent=True,
        readonly=True,
        copy=False,
        help="Multiplier applied to the expenses (or the revenue, depending on "
        "the weight basis of the company) of the plan, computed for the "
        "current company by the last full-cost recomputation.",
    )

    @api.constrains("full_cost_role", "parent_id")
    def _check_productive_not_under_reproductive(self):
        for plan in self:
            children = plan.children_ids.filtered(
                lambda child: child.full_cost_role == "productive"
            )
            if plan.full_cost_role == "reproductive" and children:
                raise ValidationError(
                    self.env._(
                        "A reproductive analytic plan cannot have productive "
                        "child plans.\n\nPlan: %(plan)s\nProductive children: "
                        "%(children)s",
                        plan=plan.display_name,
                        children=", ".join(children.mapped("display_name")),
                    )
                )
            if (
                plan.full_cost_role == "productive"
                and plan.parent_id.full_cost_role == "reproductive"
            ):
                raise ValidationError(
                    self.env._(
                        "A productive analytic plan cannot be placed under a "
                        "reproductive analytic plan.\n\nPlan: %(plan)s\n"
                        "Parent: %(parent)s",
                        plan=plan.display_name,
                        parent=plan.parent_id.display_name,
                    )
                )

    def write(self, vals):
        res = super().write(vals)
        if {"full_cost_role", "parent_id"} & set(vals):
            # The role of a line depends on the role of all the ancestors of
            # the plans of its accounts.
            plans = self.search([("id", "child_of", self.ids)])
            accounts = self.env["account.analytic.account"].search(
                [("plan_id", "in", plans.ids)]
            )
            lines = self.env["account.analytic.line"].search(
                [("auto_account_id", "in", accounts.ids)]
            )
            self.env.add_to_compute(lines._fields["full_cost_role"], lines)
        return res

    def _is_excluded_from_full_cost(self):
        self.ensure_one()
        if self.full_cost_role == "not_analyzed":
            return True
        return bool(self.parent_id) and self.parent_id._is_excluded_from_full_cost()

    def _get_direct_amounts(self, company, date_from, date_to):
        """Return ``(base_weights, net_costs)``, two {plan_id: amount} dicts
        computed from the analytic lines directly linked to accounts of each
        plan, in every analytic column:

        - base weight: absolute amount of the lines that carry the full cost
          load, the expenses or the revenue depending on the company;
        - net cost: opposite of the balance of all the lines.
        """
        line_model = self.env["account.analytic.line"]
        domain = [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        base_domain = line_model._get_full_cost_base_domain(company)
        base_weights = defaultdict(float)
        net_costs = defaultdict(float)
        for fname in line_model._get_plan_fnames():
            plan_domain = domain + [(fname, "!=", False)]
            for account, amount in line_model._read_group(
                plan_domain + base_domain, groupby=[fname], aggregates=["amount:sum"]
            ):
                base_weights[account.plan_id.id] += abs(amount)
            for account, amount in line_model._read_group(
                plan_domain, groupby=[fname], aggregates=["amount:sum"]
            ):
                net_costs[account.plan_id.id] -= amount
        return base_weights, net_costs

    @api.model
    def _compute_full_cost_multipliers(self, company, date_to):
        """Return {plan_id: multiplier} for every analytic plan.

        At every level, the net cost of the reproductive child plans is spread
        over the base lines (expenses or revenue) of the productive plans
        below, proportionally to their amount. The rates of all the levels
        above a plan add up, and the multiplier of its base lines is
        ``1 + rate`` for expenses (the cost grows) and ``1 - rate`` for
        revenue (the margin shrinks), so that the full cost of all the lines
        adds up to their amount. The cost of a level without base lines below
        goes up to the parent level."""
        date_from = self._get_full_cost_period_start(company, date_to)
        plans = self.search([])
        base_weights, net_costs = plans._get_direct_amounts(
            company, date_from, date_to
        )
        excluded = plans.filtered(lambda plan: plan._is_excluded_from_full_cost())
        productive = (
            plans.filtered(lambda plan: plan.full_cost_role == "productive") - excluded
        )
        reproductive = (
            plans.filtered(lambda plan: plan.full_cost_role == "reproductive")
            - excluded
        )

        @cache
        def base_weight(plan):
            return base_weights[plan.id] + sum(
                base_weight(child) for child in plan.children_ids & productive
            )

        @cache
        def reproductive_cost(plan):
            return net_costs[plan.id] + sum(
                reproductive_cost(child) for child in plan.children_ids & reproductive
            )

        @cache
        def level_cost(plan):
            """Reproductive cost to spread at the level of the plan."""
            return sum(
                reproductive_cost(child) for child in plan.children_ids & reproductive
            ) + sum(
                level_cost(child)
                for child in plan.children_ids & productive
                if not base_weight(child)
            )

        rates = {}

        def set_rates(plan, rate):
            if base_weight(plan):
                rate += level_cost(plan) / base_weight(plan)
            rates[plan.id] = rate
            for child in plan.children_ids & productive:
                set_rates(child, rate)

        for root in productive.filtered(lambda plan: not plan.parent_id):
            set_rates(root, 0.0)

        sign = -1.0 if company.full_cost_weight_basis == "revenue" else 1.0
        multipliers = {}
        for plan in plans:
            if plan in reproductive:
                multipliers[plan.id] = 0.0
            elif plan in productive:
                multipliers[plan.id] = 1.0 + sign * rates[plan.id]
            else:
                multipliers[plan.id] = 1.0
        return multipliers

    @api.model
    def _recompute_full_cost_multipliers(self, company=None, date_to=False):
        company = company or self.env.company
        date_to = fields.Date.to_date(date_to or fields.Date.context_today(self))
        multipliers = self.sudo()._compute_full_cost_multipliers(company, date_to)
        plans = self.sudo().with_company(company).browse(list(multipliers))
        for plan in plans:
            plan.full_cost_multiplier = multipliers[plan.id]

    @api.model
    def _recompute_full_cost(self, company, recompute_lines=True, date_to=False):
        date_to = fields.Date.to_date(date_to or fields.Date.context_today(self))
        self._recompute_full_cost_multipliers(company=company, date_to=date_to)
        if recompute_lines:
            date_from = self._get_full_cost_period_start(company, date_to)
            self.env["account.analytic.line"].search(
                [
                    ("company_id", "=", company.id),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                ]
            ).recompute_full_cost_amount()

    @api.model
    def _cron_recompute_full_cost(self):
        for company in self.env["res.company"].search([]):
            self.with_company(company)._recompute_full_cost(company)

    @api.model
    def _get_full_cost_period_start(self, company, date_to):
        method = company.full_cost_period or "biannual"

        if method == "fiscal_year":
            return company.compute_fiscalyear_dates(date_to)["date_from"]

        year_windows = {
            "annual": 1,
            "biannual": 2,
            "triannual": 3,
        }
        if method in year_windows:
            try:
                return date_to.replace(year=date_to.year - year_windows[method])
            except ValueError:
                return date_to.replace(
                    year=date_to.year - year_windows[method],
                    day=28,
                )

        if method == "monthly":
            month = date_to.month - 1
            year = date_to.year
            if month == 0:
                month = 12
                year -= 1
            while True:
                try:
                    return date_to.replace(year=year, month=month)
                except ValueError:
                    date_to -= timedelta(days=1)

        days = int(company.full_cost_window_days or 30)
        if days <= 0:
            days = 30
        return date_to - timedelta(days=days - 1)
