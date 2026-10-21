# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

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
        help="Multiplier computed for the current company by the last "
        "full-cost recomputation.",
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

    def _get_direct_weights(self, company, date_from, date_to):
        """Return {plan_id: weight} with the weight of the analytic lines
        directly linked to accounts of each plan, in every analytic column."""
        line_model = self.env["account.analytic.line"]
        if company.full_cost_weight_basis == "revenue":
            amount_domain = [("amount", ">", 0)]
            sign = 1.0
        else:
            amount_domain = [("amount", "<", 0)]
            sign = -1.0
        base_domain = [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ] + amount_domain
        weights = {}
        for fname in line_model._get_plan_fnames():
            groups = line_model._read_group(
                base_domain + [(fname, "!=", False)],
                groupby=[fname],
                aggregates=["amount:sum"],
            )
            for account, amount in groups:
                plan_id = account.plan_id.id
                weights[plan_id] = weights.get(plan_id, 0.0) + sign * amount
        return weights

    @api.model
    def _compute_full_cost_multipliers(self, company, date_to):
        """Return {plan_id: multiplier} for every analytic plan."""
        date_from = self._get_full_cost_period_start(company, date_to)
        plans = self.search([])
        direct_weights = plans._get_direct_weights(company, date_from, date_to)
        excluded = plans.filtered(lambda plan: plan._is_excluded_from_full_cost())
        subtree_weights = {}

        def subtree_weight(plan):
            if plan.id not in subtree_weights:
                subtree_weights[plan.id] = (
                    0.0
                    if plan in excluded
                    else direct_weights.get(plan.id, 0.0)
                    + sum(subtree_weight(child) for child in plan.children_ids)
                )
            return subtree_weights[plan.id]

        multipliers = {}

        def multiplier(plan):
            if plan.id in multipliers:
                return multipliers[plan.id]
            if plan in excluded:
                value = 1.0
            elif plan.full_cost_role == "reproductive":
                value = 0.0
            else:
                children = plan.children_ids - excluded
                reproductive = sum(
                    subtree_weight(child)
                    for child in children
                    if child.full_cost_role == "reproductive"
                )
                productive = direct_weights.get(plan.id, 0.0) + sum(
                    subtree_weight(child)
                    for child in children
                    if child.full_cost_role == "productive"
                )
                value = (
                    (productive + reproductive) / productive if productive else 1.0
                )
                if plan.parent_id:
                    value *= multiplier(plan.parent_id)
            multipliers[plan.id] = value
            return value

        for plan in plans:
            multiplier(plan)
        return multipliers

    @api.model
    def recompute_full_cost_multipliers(self, company=None, date_to=False):
        company = company or self.env.company
        date_to = fields.Date.to_date(date_to or fields.Date.context_today(self))
        multipliers = self.sudo()._compute_full_cost_multipliers(company, date_to)
        plans = self.sudo().with_company(company).browse(list(multipliers))
        for plan in plans:
            plan.full_cost_multiplier = multipliers[plan.id]

    @api.model
    def _recompute_full_cost(self, company, recompute_lines=True, date_to=False):
        date_to = fields.Date.to_date(date_to or fields.Date.context_today(self))
        self.recompute_full_cost_multipliers(company=company, date_to=date_to)
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
