# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticPlanLevelList(HttpCase):
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
        action = cls.env.ref("analytic.account_analytic_line_action_entries")
        action.write(
            {
                "domain": [("name", "=like", "Tour %")],
                "context": {
                    "search_default_group_by_analytic_plan_level_1": 1,
                    "search_default_group_by_analytic_plan_level_2": 2,
                    "search_default_group_by_analytic_account": 3,
                },
            }
        )

    def test_empty_plan_levels_are_skipped(self):
        self.start_tour(
            "/odoo/action-analytic.account_analytic_line_action_entries",
            "analytic_plan_level_list_tour",
            login="admin",
        )
