from odoo import api, fields, models

PLAN_LEVEL_FIELDS = [
    "analytic_plan_level_0_id",
    "analytic_plan_level_1_id",
    "analytic_plan_level_2_id",
    "analytic_plan_level_3_id",
    "analytic_plan_level_4_id",
]


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    analytic_plan_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan",
        compute="_compute_analytic_plan_id",
        store=True,
        index=True,
    )
    analytic_plan_level_0_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan (Root)",
        compute="_compute_analytic_plan_levels",
        store=True,
        index=True,
    )
    analytic_plan_level_1_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan (Level 1)",
        compute="_compute_analytic_plan_levels",
        store=True,
        index=True,
    )
    analytic_plan_level_2_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan (Level 2)",
        compute="_compute_analytic_plan_levels",
        store=True,
        index=True,
    )
    analytic_plan_level_3_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan (Level 3)",
        compute="_compute_analytic_plan_levels",
        store=True,
        index=True,
    )
    analytic_plan_level_4_id = fields.Many2one(
        comodel_name="account.analytic.plan",
        string="Analytic Plan (Level 4)",
        compute="_compute_analytic_plan_levels",
        store=True,
        index=True,
    )

    @api.depends("account_id", "account_id.plan_id.show_in_analytic_searchpanel")
    def _compute_analytic_plan_id(self):
        for line in self:
            plan = line.account_id.plan_id
            line.analytic_plan_id = (
                plan if plan.show_in_analytic_searchpanel else False
            )

    @api.depends("analytic_plan_id", "analytic_plan_id.parent_path")
    def _compute_analytic_plan_levels(self):
        """Split the plan hierarchy top-down: level 0 is always the root plan,
        so grouping by consecutive levels unfolds the hierarchy consistently
        whatever the depth of the plan of each line."""
        for line in self:
            parent_path = line.analytic_plan_id.parent_path or ""
            plan_ids = [int(plan_id) for plan_id in parent_path.split("/") if plan_id]
            for level, fname in enumerate(PLAN_LEVEL_FIELDS):
                line[fname] = plan_ids[level] if level < len(plan_ids) else False
