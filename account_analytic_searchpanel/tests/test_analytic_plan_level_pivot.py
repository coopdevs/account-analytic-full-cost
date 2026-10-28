# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticPlanLevelPivot(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.user_admin").groups_id += cls.env.ref(
            "analytic.group_analytic_accounting"
        )
        Plan = cls.env["account.analytic.plan"]
        root, _other_plans = Plan._get_all_plans()
        shallow = Plan.create({"name": "Tour Shallow Plan", "parent_id": root.id})
        deep = Plan.create({"name": "Tour Deep Plan", "parent_id": root.id})
        deep_sub = Plan.create({"name": "Tour Deep Subplan", "parent_id": deep.id})
        for plan, account_name in (
            (shallow, "Tour Shallow Account"),
            (deep_sub, "Tour Deep Account"),
        ):
            account = cls.env["account.analytic.account"].create(
                {"name": account_name, "plan_id": plan.id}
            )
            cls.env["account.analytic.line"].create(
                {"name": f"Tour {account_name}", "account_id": account.id}
            )
        cls.action = cls.env["ir.actions.act_window"].create(
            {
                "name": "Plan Level Pivot",
                "res_model": "account.analytic.line",
                "view_mode": "pivot",
                "view_id": cls.env.ref("analytic.view_account_analytic_line_pivot").id,
                "domain": "[('name', '=like', 'Tour %')]",
                "context": {
                    "pivot_row_groupby": [
                        "analytic_plan_level_1_id",
                        "analytic_plan_level_2_id",
                        "analytic_plan_level_3_id",
                        "account_id",
                    ],
                },
            }
        )

    def test_empty_plan_levels_are_skipped_in_pivot(self):
        self.start_tour(
            f"/odoo/action-{self.action.id}",
            "analytic_plan_level_pivot_tour",
            login="admin",
        )
