# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, fields, models
from odoo.osv import expression

from .analytic_plan import FULL_COST_ROLES


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    full_cost_role = fields.Selection(
        FULL_COST_ROLES,
        compute="_compute_full_cost_role",
        string="Full Cost Role",
        store=True,
        readonly=True,
    )
    full_cost_amount = fields.Monetary(
        string="Full Cost Amount",
        currency_field="currency_id",
        readonly=True,
        copy=False,
        help="Amount after applying the analytic plan full cost multiplier.",
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

    @api.model
    def _get_full_cost_trigger_fnames(self):
        return {"amount", "date", "company_id", *self._get_plan_fnames()}

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.recompute_full_cost_amount()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if set(self._get_plan_fnames()) & set(vals):
            # Plan columns are dynamic, so they cannot be declared in the
            # dependencies of the role.
            self.env.add_to_compute(self._fields["full_cost_role"], self)
        if self._get_full_cost_trigger_fnames() & set(vals):
            self.recompute_full_cost_amount()
        return res

    def _get_full_cost_windows(self):
        """Return {company: (date_from, date_to)} for the current window of
        every allowed company."""
        date_to = fields.Date.context_today(self)
        plan_model = self.env["account.analytic.plan"]
        return {
            company: (plan_model._get_full_cost_period_start(company, date_to), date_to)
            for company in self.env.companies
        }

    def _compute_is_in_full_cost_window(self):
        windows = {
            company.id: window
            for company, window in self._get_full_cost_windows().items()
        }
        for line in self:
            window = windows.get(line.company_id.id)
            line.is_in_full_cost_window = bool(
                window and line.date and window[0] <= line.date <= window[1]
            )

    def _search_is_in_full_cost_window(self, operator, value):
        if operator not in ("=", "!="):
            raise NotImplementedError(
                self.env._("Unsupported operator %s", operator)
            )
        domain = expression.OR(
            [
                [
                    ("company_id", "=", company.id),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                ]
                for company, (date_from, date_to) in (
                    self._get_full_cost_windows().items()
                )
            ]
        )
        positive = (operator == "=") == bool(value)
        return domain if positive else ["!", *domain]

    @api.depends("account_id")
    def _compute_full_cost_role(self):
        for line in self:
            line.full_cost_role = line._get_full_cost_role()

    def _get_included_full_cost_plans(self):
        self.ensure_one()
        return (
            self._get_analytic_accounts()
            .mapped("plan_id")
            .filtered(lambda plan: not plan._is_excluded_from_full_cost())
        )

    def _get_full_cost_role(self):
        self.ensure_one()
        plans = self._get_included_full_cost_plans()
        if not plans:
            return "not_analyzed"
        if any(plan.full_cost_role == "reproductive" for plan in plans):
            return "reproductive"
        return "productive"

    def _get_full_cost_values(self):
        self.ensure_one()
        base_amount = self.amount or 0.0
        if base_amount > 0:
            return base_amount, 1.0
        plans = self._get_included_full_cost_plans().with_company(self.company_id)
        if not plans:
            return base_amount, 1.0
        if any(plan.full_cost_role == "reproductive" for plan in plans):
            return 0.0, 0.0
        multiplier = 1.0
        for plan in plans:
            multiplier *= plan.full_cost_multiplier or 1.0
        return base_amount * multiplier, multiplier

    def recompute_full_cost_amount(self):
        lines_by_values = defaultdict(lambda: self.browse())
        for line in self:
            amount, multiplier = line._get_full_cost_values()
            if (
                line.currency_id.compare_amounts(line.full_cost_amount, amount)
                or line.full_cost_multiplier_snapshot != multiplier
            ):
                lines_by_values[(amount, multiplier)] |= line
        for (amount, multiplier), lines in lines_by_values.items():
            lines.write(
                {
                    "full_cost_amount": amount,
                    "full_cost_multiplier_snapshot": multiplier,
                }
            )
