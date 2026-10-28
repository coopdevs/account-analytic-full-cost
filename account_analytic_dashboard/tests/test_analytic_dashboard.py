# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticDashboard(TransactionCase):
    def test_revenue_and_expenses_are_split_by_sign(self):
        Plan = self.env["account.analytic.plan"]
        root, _other_plans = Plan._get_all_plans()
        account = self.env["account.analytic.account"].create(
            {"name": "Split Account", "plan_id": root.id}
        )
        lines = self.env["account.analytic.line"].create(
            [
                {"name": "Split revenue", "account_id": account.id, "amount": 300.0},
                {"name": "Split expense", "account_id": account.id, "amount": -100.0},
            ]
        )

        self.assertEqual(lines.mapped("amount_revenue"), [300.0, 0.0])
        self.assertEqual(lines.mapped("amount_expense"), [0.0, -100.0])

        lines[0].amount = -20.0
        self.assertEqual(lines[0].amount_revenue, 0.0)
        self.assertEqual(lines[0].amount_expense, -20.0)

    def test_personnel_cost_source(self):
        company = self.env.company
        Plan = self.env["account.analytic.plan"]
        root, _other_plans = Plan._get_all_plans()
        account = self.env["account.analytic.account"].create(
            {"name": "Source Account", "plan_id": root.id}
        )
        payroll_account = self.env["account.account"].create(
            {"name": "Salaries", "code": "640099", "account_type": "expense"}
        )
        sale_account = self.env["account.account"].create(
            {"name": "Sales", "code": "700099", "account_type": "income"}
        )
        Line = self.env["account.analytic.line"]
        timesheet, payroll, sale = Line.create(
            [
                {"name": "Timesheet", "account_id": account.id, "amount": -50.0},
                {
                    "name": "Payroll",
                    "account_id": account.id,
                    "amount": -60.0,
                    "general_account_id": payroll_account.id,
                },
                {
                    "name": "Sale",
                    "account_id": account.id,
                    "amount": 200.0,
                    "general_account_id": sale_account.id,
                },
            ]
        )
        lines = timesheet + payroll + sale

        def included():
            lines.invalidate_recordset(["analytic_report_included"])
            searched = Line.search(
                [("id", "in", lines.ids), ("analytic_report_included", "=", True)]
            )
            self.assertEqual(searched, lines.filtered("analytic_report_included"))
            return searched

        company.analytic_report_personnel_cost = "accounting"
        self.assertEqual(included(), payroll + sale)

        company.write(
            {
                "analytic_report_personnel_cost": "timesheets",
                "analytic_report_personnel_account_ids": [(6, 0, payroll_account.ids)],
            }
        )
        self.assertEqual(included(), timesheet + sale)

        company.analytic_report_personnel_cost = "all"
        self.assertEqual(included(), lines)

    def test_dashboard_only_uses_existing_fields(self):
        """A missing field only shows up as #ERROR cells in the dashboard."""
        dashboard = self.env.ref("account_analytic_dashboard.dashboard_analytic")
        data = json.loads(base64.b64decode(dashboard.spreadsheet_binary_data))
        for pivot in data["pivots"].values():
            fields = self.env[pivot["model"]]._fields
            used = (
                [dimension["fieldName"] for dimension in pivot["rows"]]
                + [dimension["fieldName"] for dimension in pivot["columns"]]
                + [measure["fieldName"] for measure in pivot["measures"]]
                + [leaf[0] for leaf in pivot["domain"] if isinstance(leaf, list)]
                + [match["chain"] for match in pivot["fieldMatching"].values()]
            )
            for fname in used:
                self.assertIn(fname, fields, f"Pivot {pivot['name']}: {fname}")
            # Its records are opened with the analytic views
            self.assertEqual(
                self.env.ref(pivot["actionXmlId"]),
                self.env.ref("account_analytic_dashboard.action_analytic_monthly_report"),
            )

    def test_records_are_opened_with_analytic_views(self):
        """Not with the default views of the model, which may be the timesheet
        ones, without the analytic amount."""
        action = self.env.ref(
            "account_analytic_dashboard.action_analytic_monthly_report"
        )
        views = dict(
            (view_type, view_id)
            for view_id, view_type in action._get_action_dict()["views"]
        )
        self.assertEqual(
            views["list"], self.env.ref("analytic.view_account_analytic_line_tree").id
        )
        self.assertEqual(
            views["form"], self.env.ref("analytic.view_account_analytic_line_form").id
        )


@tagged("post_install", "-at_install")
class TestAnalyticDashboardTour(HttpCase):
    def test_dashboard_renders(self):
        self.env.ref("base.user_admin").groups_id += self.env.ref(
            "analytic.group_analytic_accounting"
        )
        self.start_tour(
            "/odoo/action-spreadsheet_dashboard.ir_actions_dashboard_action",
            "analytic_dashboard_tour",
            login="admin",
        )
