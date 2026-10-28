# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticPlanLevels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Plan = cls.env["account.analytic.plan"]
        # Only the project plan column (account_id) is split into levels
        cls.root, _other_plans = Plan._get_all_plans()
        cls.child = Plan.create({"name": "Levels Child", "parent_id": cls.root.id})
        cls.grandchild = Plan.create(
            {"name": "Levels Grandchild", "parent_id": cls.child.id}
        )
        cls.other_child = Plan.create(
            {"name": "Levels Other Child", "parent_id": cls.root.id}
        )

    def _create_line(self, plan):
        account = self.env["account.analytic.account"].create(
            {"name": f"{plan.name} Account", "plan_id": plan.id}
        )
        return self.env["account.analytic.line"].create(
            {
                "name": f"{plan.name} Line",
                plan._column_name(): account.id,
                "amount": -10.0,
            }
        )

    def _get_levels(self, line):
        return [
            line.analytic_plan_level_0_id,
            line.analytic_plan_level_1_id,
            line.analytic_plan_level_2_id,
            line.analytic_plan_level_3_id,
            line.analytic_plan_level_4_id,
        ]

    def test_levels_are_counted_from_root(self):
        Plan = self.env["account.analytic.plan"]
        line = self._create_line(self.grandchild)
        self.assertEqual(
            self._get_levels(line),
            [self.root, self.child, self.grandchild, Plan, Plan],
        )

    def test_root_plan_line_only_fills_root_level(self):
        Plan = self.env["account.analytic.plan"]
        line = self._create_line(self.root)
        self.assertEqual(self._get_levels(line), [self.root, Plan, Plan, Plan, Plan])

    def test_levels_follow_plan_moves(self):
        Plan = self.env["account.analytic.plan"]
        line = self._create_line(self.grandchild)
        self.grandchild.parent_id = self.other_child
        self.assertEqual(
            self._get_levels(line),
            [self.root, self.other_child, self.grandchild, Plan, Plan],
        )

    def test_hidden_plan_has_no_levels(self):
        line = self._create_line(self.grandchild)
        self.grandchild.show_in_analytic_searchpanel = False
        self.assertFalse(line.analytic_plan_id)
        self.assertFalse(line.analytic_plan_level_0_id)
