from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    full_cost_role = fields.Selection(
        [
            ("productive", "Productive"),
            ("reproductive", "Reproductive"),
            ("not_analyzed", "Not Analyzed"),
        ],
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

    full_cost_multiplier = fields.Float(string="Full Cost Multiplier")

    @api.constrains("full_cost_role", "parent_id")
    def _check_productive_not_under_reproductive(self):
        for plan in self:
            if (
                plan.full_cost_role == "productive"
                and plan.parent_id
                and plan.parent_id.full_cost_role == "reproductive"
            ):
                raise ValidationError(
                    _(
                        "A productive analytic plan cannot be placed under a "
                        "reproductive analytic plan.\n\n"
                        "Plan: %(plan)s\n"
                        "Parent: %(parent)s"
                    )
                    % {"plan": plan.display_name, "parent": plan.parent_id.display_name}
                )

    def _get_direct_weight(self, company, date_from, date_to):
        self.ensure_one()
        account_field = self._column_name()
        weight_basis = company.full_cost_weight_basis or "expenses"

        domain = [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            (f"{account_field}.plan_id", "=", self.id),
        ]
        lines = self.env["account.analytic.line"]

        if weight_basis == "revenue":
            return sum(lines.search(domain + [("amount", ">", 0)]).mapped("amount"))

        return -sum(lines.search(domain + [("amount", "<", 0)]).mapped("amount"))

    def _is_excluded_from_full_cost(self):
        self.ensure_one()
        if self.full_cost_role == "not_analyzed":
            return True
        if self.parent_id:
            return self.parent_id._is_excluded_from_full_cost()
        return False

    def _get_subtree_weight(self, company, date_from, date_to):
        value = 0.0
        for plan in self:
            if plan.full_cost_role == "not_analyzed":
                continue
            value += plan._get_direct_weight(
                company, date_from, date_to
            ) + plan.children_ids._get_subtree_weight(company, date_from, date_to)

        return value

    def _get_ancestor_multiplier(self, isolated_multipliers):
        self.ensure_one()
        if self.parent_id:
            return isolated_multipliers.get(
                self.parent_id.id, 1.0
            ) * self.parent_id._get_ancestor_multiplier(isolated_multipliers)
        return 1.0

    @api.model
    def recompute_full_cost_multipliers(self, company=None, date_to=False):
        company = (company or self.env.company).sudo()
        date_to = fields.Date.to_date(date_to or fields.Date.context_today(self))
        date_from = self._get_full_cost_period_start(company, date_to)

        plans = self.env["account.analytic.plan"].search([])
        included_plans = plans.filtered(
            lambda plan: not plan._is_excluded_from_full_cost()
        )
        weight_by_plan = {
            plan.id: plan._get_subtree_weight(company, date_from, date_to)
            for plan in included_plans
        }

        isolated_multipliers = {}
        for plan in included_plans:
            reproductive_weight = sum(
                weight_by_plan[child.id]
                for child in plan.children_ids
                if child.full_cost_role == "reproductive"
            )
            productive_weight = sum(
                weight_by_plan[child.id]
                for child in plan.children_ids
                if child.full_cost_role == "productive"
            )

            if plan.full_cost_role == "productive":
                productive_weight += plan._get_direct_weight(
                    company, date_from, date_to
                )

            if plan.full_cost_role == "reproductive":
                isolated_multipliers[plan.id] = 0.0
            else:
                isolated_multipliers[plan.id] = (
                    (reproductive_weight + productive_weight) / productive_weight
                    if productive_weight
                    else 1.0
                )

        multiplier_by_plan = {}
        for plan in plans:
            if plan._is_excluded_from_full_cost():
                multiplier_by_plan[plan.id] = 1.0
            else:
                multiplier_by_plan[plan.id] = isolated_multipliers.get(
                    plan.id, 1.0
                ) * plan._get_ancestor_multiplier(isolated_multipliers)
            plan.full_cost_multiplier = multiplier_by_plan[plan.id]

    @api.model
    def _get_full_cost_period_start(self, company, date_to):
        method = company.full_cost_period or "biannual"

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
