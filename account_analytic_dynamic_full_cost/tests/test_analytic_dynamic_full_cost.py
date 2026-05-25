# Copyright (C) 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticDynamicFullCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Plan = cls.env["account.analytic.plan"]
        cls.Account = cls.env["account.analytic.account"]
        cls.Line = cls.env["account.analytic.line"]
        cls.Report = cls.env["account.analytic.full.cost.report"]
        cls.reference_date = date(2025, 5, 15)
        cls.company.write(
            {
                "full_cost_period": "annual",
                "full_cost_weight_basis": "expenses",
                "full_cost_window_days": 365,
            }
        )

    def _create_plan(self, name, full_cost_role="productive", parent=False):
        return self.Plan.create(
            {
                "name": name,
                "full_cost_role": full_cost_role,
                "parent_id": parent.id if parent else False,
            }
        )

    def _create_account(self, name, plan):
        return self.Account.create(
            {
                "name": name,
                "plan_id": plan.id,
                "company_id": self.company.id,
            }
        )

    def _create_line(self, name, account, amount, line_date=False):
        return self.Line.create(
            {
                "name": name,
                "date": line_date or self.reference_date,
                "company_id": self.company.id,
                account.plan_id._column_name(): account.id,
                "amount": amount,
            }
        )

    def _create_multidimensional_line(self, name, accounts, amount):
        values = {
            "name": name,
            "date": self.reference_date,
            "company_id": self.company.id,
            "amount": amount,
        }
        for account in accounts:
            values[account.plan_id._column_name()] = account.id
        return self.Line.create(values)

    def test_line_without_analyzed_plan_keeps_original_amount(self):
        line = self.Line.new(
            {
                "name": "No analytic plan",
                "date": self.reference_date,
                "company_id": self.company.id,
                "amount": -42.0,
            }
        )

        line.recompute_full_cost_amount()

        self.assertEqual(line.full_cost_role, "not_analyzed")
        self.assertAlmostEqual(line.full_cost_amount, -42.0)

    def test_line_without_company_keeps_original_amount(self):
        plan = self._create_plan("No Company Plan")
        account = self._create_account("No Company Account", plan)
        line = self.Line.new(
            {
                "name": "No company",
                "date": self.reference_date,
                account.plan_id._column_name(): account.id,
                "amount": -75.0,
            }
        )
        plan.full_cost_multiplier = 2.5

        line.recompute_full_cost_amount()

        self.assertAlmostEqual(line.full_cost_amount, -75.0)

    def test_zero_productive_weight_uses_neutral_multiplier(self):
        root = self._create_plan("Zero Weight Root")
        productive = self._create_plan("Zero Weight Productive", parent=root)
        overhead = self._create_plan(
            "Zero Weight Overhead", full_cost_role="reproductive", parent=root
        )
        overhead_account = self._create_account("Zero Weight Overhead", overhead)
        overhead_line = self._create_line("Overhead only", overhead_account, -100.0)

        self.Plan.recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        overhead_line.recompute_full_cost_amount()

        self.assertAlmostEqual(root.full_cost_multiplier, 1.0)
        self.assertAlmostEqual(productive.full_cost_multiplier, 1.0)
        self.assertAlmostEqual(overhead.full_cost_multiplier, 0.0)
        self.assertAlmostEqual(overhead_line.full_cost_amount, 0.0)

    def test_lines_outside_reference_period_are_ignored(self):
        root = self._create_plan("Monthly Root")
        productive = self._create_plan("Monthly Productive", parent=root)
        overhead = self._create_plan(
            "Monthly Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account("Monthly Productive", productive)
        overhead_account = self._create_account("Monthly Overhead", overhead)

        current_line = self._create_line(
            "Current productive", productive_account, -100.0
        )
        self._create_line(
            "Old productive",
            productive_account,
            -900.0,
            line_date=date(2025, 4, 14),
        )
        self._create_line("Current overhead", overhead_account, -100.0)
        self._create_line(
            "Old overhead",
            overhead_account,
            -900.0,
            line_date=date(2025, 4, 14),
        )
        self.company.full_cost_period = "monthly"

        self.Plan.recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        current_line.recompute_full_cost_amount()

        self.assertAlmostEqual(root.full_cost_multiplier, 2.0)
        self.assertAlmostEqual(productive.full_cost_multiplier, 2.0)
        self.assertAlmostEqual(current_line.full_cost_amount, -200.0)

    def test_non_positive_rolling_window_days_falls_back_to_thirty_days(self):
        self.company.write(
            {
                "full_cost_period": "rolling",
                "full_cost_window_days": 0,
            }
        )

        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2025, 4, 16),
        )

    def test_recompute_defaults_to_environment_company_and_today(self):
        today = fields.Date.context_today(self.Plan)
        root = self._create_plan("Default Recompute Root")
        productive = self._create_plan("Default Recompute Productive", parent=root)
        overhead = self._create_plan(
            "Default Recompute Overhead",
            full_cost_role="reproductive",
            parent=root,
        )
        productive_account = self._create_account(
            "Default Recompute Productive", productive
        )
        overhead_account = self._create_account("Default Recompute Overhead", overhead)
        productive_line = self._create_line(
            "Default recompute productive",
            productive_account,
            -100.0,
            line_date=today,
        )
        self._create_line(
            "Default recompute overhead",
            overhead_account,
            -50.0,
            line_date=today,
        )

        self.Plan.recompute_full_cost_multipliers(
            company=False,
            date_to=False,
        )
        productive_line.recompute_full_cost_amount()

        self.assertAlmostEqual(root.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(productive_line.full_cost_amount, -150.0)

    def test_wizard_default_get_sets_company(self):
        values = self.env[
            "account.analytic.full.cost.recompute.wizard"
        ].default_get(["company_id"])

        self.assertEqual(values["company_id"], self.company.id)

    def test_historical_report_uses_analysis_date_window(self):
        self.company.write(
            {
                "full_cost_period": "rolling",
                "full_cost_window_days": 31,
            }
        )
        root = self._create_plan("Report Root")
        productive = self._create_plan("Report Productive", parent=root)
        overhead = self._create_plan(
            "Report Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account("Report Productive", productive)
        overhead_account = self._create_account("Report Overhead", overhead)

        april_productive = self._create_line(
            "April productive",
            productive_account,
            -100.0,
            line_date=date(2025, 4, 14),
        )
        self._create_line(
            "April overhead",
            overhead_account,
            -50.0,
            line_date=date(2025, 4, 14),
        )
        may_productive = self._create_line(
            "May productive",
            productive_account,
            -100.0,
            line_date=date(2025, 5, 15),
        )
        self._create_line(
            "May overhead",
            overhead_account,
            -50.0,
            line_date=date(2025, 5, 15),
        )

        report = self.Report.search(
            [
                ("company_id", "=", self.company.id),
                ("analysis_date", "=", self.reference_date),
            ]
        )
        report_line = report.filtered(lambda item: item.line_id == may_productive)

        self.assertNotIn(april_productive.id, report.mapped("line_id").ids)
        self.assertIn(may_productive.id, report.mapped("line_id").ids)
        self.assertEqual(report_line.window_start, date(2025, 4, 15))
        self.assertAlmostEqual(report_line.full_cost_amount, -150.0)

    def test_historical_analysis_wizard_opens_selected_date_report(self):
        root = self._create_plan("Analysis Wizard Root")
        productive = self._create_plan("Analysis Wizard Productive", parent=root)
        overhead = self._create_plan(
            "Analysis Wizard Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account(
            "Analysis Wizard Productive", productive
        )
        overhead_account = self._create_account("Analysis Wizard Overhead", overhead)
        productive_line = self._create_line(
            "Analysis wizard productive", productive_account, -100.0
        )
        self._create_line("Analysis wizard overhead", overhead_account, -50.0)
        wizard = self.env["account.analytic.full.cost.analysis.wizard"].create(
            {
                "company_id": self.company.id,
                "analysis_date": self.reference_date,
            }
        )

        action = wizard.action_open_report()

        self.assertEqual(action["res_model"], "account.analytic.full.cost.report")
        self.assertEqual(
            action["domain"],
            [
                ("company_id", "=", self.company.id),
                ("analysis_date", "=", self.reference_date),
            ],
        )
        report_line = self.Report.search(
            [
                ("analysis_date", "=", self.reference_date),
                ("line_id", "=", productive_line.id),
            ]
        )
        self.assertAlmostEqual(report_line.full_cost_amount, -150.0)

    def test_historical_report_uses_company_period_configuration(self):
        self.company.full_cost_period = "annual"
        root = self._create_plan("Configured Period Root")
        productive = self._create_plan("Configured Period Productive", parent=root)
        overhead = self._create_plan(
            "Configured Period Overhead",
            full_cost_role="reproductive",
            parent=root,
        )
        productive_account = self._create_account(
            "Configured Period Productive", productive
        )
        overhead_account = self._create_account("Configured Period Overhead", overhead)
        self._create_line(
            "April productive",
            productive_account,
            -100.0,
            line_date=date(2025, 4, 15),
        )
        self._create_line(
            "April overhead",
            overhead_account,
            -100.0,
            line_date=date(2025, 4, 15),
        )
        may_line = self._create_line(
            "May productive",
            productive_account,
            -100.0,
            line_date=self.reference_date,
        )
        report_line = self.Report.search(
            [
                ("analysis_date", "=", self.reference_date),
                ("line_id", "=", may_line.id),
            ]
        )

        self.assertAlmostEqual(report_line.full_cost_amount, -150.0)

    def test_full_cost_multiplier_includes_direct_productive_plan_weight(self):
        root = self._create_plan("Full Cost Root")
        child = self._create_plan("Full Cost Child", parent=root)
        overhead = self._create_plan(
            "Full Cost Overhead", full_cost_role="reproductive", parent=root
        )

        root_account = self._create_account("Root Direct Work", root)
        child_account = self._create_account("Child Direct Work", child)
        overhead_account = self._create_account("Root Overhead", overhead)

        root_line = self._create_line("Root direct cost", root_account, -100.0)
        child_line = self._create_line("Child direct cost", child_account, -300.0)
        overhead_line = self._create_line("Overhead cost", overhead_account, -100.0)
        positive_line = self._create_line(
            "Positive analytic amount", child_account, 50.0
        )

        self.Plan.recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        lines = root_line + child_line + overhead_line + positive_line
        lines.recompute_full_cost_amount()

        self.assertAlmostEqual(root.full_cost_multiplier, 1.25)
        self.assertAlmostEqual(child.full_cost_multiplier, 1.25)
        self.assertAlmostEqual(overhead.full_cost_multiplier, 0.0)
        self.assertAlmostEqual(root_line.full_cost_amount, -125.0)
        self.assertAlmostEqual(child_line.full_cost_amount, -375.0)
        self.assertAlmostEqual(overhead_line.full_cost_amount, 0.0)
        self.assertAlmostEqual(positive_line.full_cost_amount, 50.0)

    def test_productive_plan_cannot_be_child_of_reproductive_plan(self):
        overhead = self._create_plan(
            "Parent Overhead", full_cost_role="reproductive"
        )

        with self.assertRaises(ValidationError):
            self._create_plan("Invalid Productive Child", parent=overhead)

    def test_not_analyzed_branch_is_excluded_with_all_descendants(self):
        root = self._create_plan("Root")
        productive = self._create_plan("Productive", parent=root)
        reproductive = self._create_plan(
            "Reproductive", full_cost_role="reproductive", parent=root
        )
        ignored = self._create_plan(
            "Ignored", full_cost_role="not_analyzed", parent=root
        )
        ignored_child = self._create_plan("Ignored Child", parent=ignored)

        productive_account = self._create_account("Productive", productive)
        reproductive_account = self._create_account("Reproductive", reproductive)
        ignored_account = self._create_account("Ignored", ignored)
        ignored_child_account = self._create_account("Ignored Child", ignored_child)

        productive_line = self._create_line(
            "Productive cost", productive_account, -100.0
        )
        reproductive_line = self._create_line(
            "Reproductive cost", reproductive_account, -100.0
        )
        ignored_line = self._create_line("Ignored cost", ignored_account, -500.0)
        ignored_child_line = self._create_line(
            "Ignored child cost", ignored_child_account, -700.0
        )

        self.Plan.recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        lines = productive_line + reproductive_line + ignored_line + ignored_child_line
        lines.recompute_full_cost_amount()

        self.assertAlmostEqual(root.full_cost_multiplier, 2.0)
        self.assertAlmostEqual(productive.full_cost_multiplier, 2.0)
        self.assertAlmostEqual(reproductive.full_cost_multiplier, 0.0)
        self.assertAlmostEqual(ignored.full_cost_multiplier, 1.0)
        self.assertAlmostEqual(ignored_child.full_cost_multiplier, 1.0)
        self.assertAlmostEqual(productive_line.full_cost_amount, -200.0)
        self.assertAlmostEqual(reproductive_line.full_cost_amount, 0.0)
        self.assertAlmostEqual(ignored_line.full_cost_amount, -500.0)
        self.assertAlmostEqual(ignored_child_line.full_cost_amount, -700.0)

    def test_full_cost_uses_dynamic_plan_columns(self):
        service_root = self._create_plan("Service Root")
        service_productive = self._create_plan(
            "Service Productive", parent=service_root
        )
        service_overhead = self._create_plan(
            "Service Overhead", full_cost_role="reproductive", parent=service_root
        )
        ignored_root = self._create_plan(
            "Ignored Dimension", full_cost_role="not_analyzed"
        )
        ignored_child = self._create_plan("Ignored Child", parent=ignored_root)

        service_productive_account = self._create_account(
            "Service Productive", service_productive
        )
        service_overhead_account = self._create_account(
            "Service Overhead", service_overhead
        )
        ignored_account = self._create_account("Ignored", ignored_child)

        productive_line = self._create_multidimensional_line(
            "Service productive cost",
            service_productive_account + ignored_account,
            -100.0,
        )
        overhead_line = self._create_multidimensional_line(
            "Service overhead cost",
            service_overhead_account + ignored_account,
            -50.0,
        )

        self.Plan.recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        productive_line.recompute_full_cost_amount()
        overhead_line.recompute_full_cost_amount()

        self.assertAlmostEqual(service_root.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(service_productive.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(service_overhead.full_cost_multiplier, 0.0)
        self.assertAlmostEqual(ignored_root.full_cost_multiplier, 1.0)
        self.assertAlmostEqual(ignored_child.full_cost_multiplier, 1.0)
        self.assertEqual(productive_line.full_cost_role, "productive")
        self.assertEqual(overhead_line.full_cost_role, "reproductive")
        self.assertAlmostEqual(productive_line.full_cost_amount, -150.0)
        self.assertAlmostEqual(overhead_line.full_cost_amount, 0.0)

    def test_full_cost_multiplier_can_be_weighted_by_revenue(self):
        self.company.full_cost_weight_basis = "revenue"
        root = self._create_plan("Revenue Root")
        productive = self._create_plan("Revenue Productive", parent=root)
        overhead = self._create_plan(
            "Revenue Overhead", full_cost_role="reproductive", parent=root
        )

        productive_account = self._create_account("Revenue Productive", productive)
        overhead_account = self._create_account("Revenue Overhead", overhead)

        productive_revenue = self._create_line(
            "Productive revenue", productive_account, 200.0
        )
        self._create_line("Productive expense", productive_account, -1000.0)
        self._create_line("Overhead revenue", overhead_account, 100.0)
        overhead_expense = self._create_line(
            "Overhead expense", overhead_account, -50.0
        )

        self.Plan.recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        (productive_revenue + overhead_expense).recompute_full_cost_amount()

        self.assertAlmostEqual(root.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(productive.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(overhead.full_cost_multiplier, 0.0)
        self.assertAlmostEqual(productive_revenue.full_cost_amount, 200.0)
        self.assertAlmostEqual(overhead_expense.full_cost_amount, 0.0)

    def test_full_cost_period_start(self):
        self.company.full_cost_period = "biannual"
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2023, 5, 15),
        )

        self.company.full_cost_period = "annual"
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2024, 5, 15),
        )

        self.company.full_cost_period = "triannual"
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2022, 5, 15),
        )

        self.company.full_cost_period = "monthly"
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2025, 4, 15),
        )

        self.company.write(
            {
                "full_cost_period": "rolling",
                "full_cost_window_days": 10,
            }
        )
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2025, 5, 6),
        )

    def test_full_cost_window_search_uses_company_configuration(self):
        self.company.full_cost_period = "annual"
        inside_line = self._create_line(
            "Inside full cost window",
            self._create_account(
                "Inside full cost window",
                self._create_plan("Inside full cost window"),
            ),
            -10.0,
            line_date=fields.Date.context_today(self.Line),
        )
        outside_line = self._create_line(
            "Outside full cost window",
            inside_line.account_id,
            -10.0,
            line_date=date(2000, 1, 1),
        )

        window_lines = self.Line.search([("is_in_full_cost_window", "=", True)])

        self.assertIn(inside_line, window_lines)
        self.assertNotIn(outside_line, window_lines)

    def test_wizard_recomputes_multipliers_and_lines(self):
        today = fields.Date.context_today(self.Plan)
        root = self._create_plan("Wizard Root")
        productive = self._create_plan("Wizard Productive", parent=root)
        overhead = self._create_plan(
            "Wizard Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account("Wizard Productive", productive)
        overhead_account = self._create_account("Wizard Overhead", overhead)
        productive_line = self._create_line(
            "Wizard productive",
            productive_account,
            -80.0,
            line_date=today,
        )
        self._create_line(
            "Wizard overhead",
            overhead_account,
            -40.0,
            line_date=today,
        )

        wizard = self.env["account.analytic.full.cost.recompute.wizard"].create(
            {
                "company_id": self.company.id,
                "recompute_lines": True,
            }
        )

        self.assertEqual(
            wizard.action_recompute(), {"type": "ir.actions.act_window_close"}
        )
        self.assertAlmostEqual(root.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(productive_line.full_cost_amount, -120.0)

    def test_wizard_can_recompute_only_multipliers(self):
        today = fields.Date.context_today(self.Plan)
        root = self._create_plan("Wizard Multiplier Root")
        productive = self._create_plan("Wizard Multiplier Productive", parent=root)
        overhead = self._create_plan(
            "Wizard Multiplier Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account(
            "Wizard Multiplier Productive", productive
        )
        overhead_account = self._create_account("Wizard Multiplier Overhead", overhead)
        productive_line = self._create_line(
            "Wizard multiplier productive",
            productive_account,
            -100.0,
            line_date=today,
        )
        self._create_line(
            "Wizard multiplier overhead",
            overhead_account,
            -100.0,
            line_date=today,
        )

        wizard = self.env["account.analytic.full.cost.recompute.wizard"].create(
            {
                "company_id": self.company.id,
                "recompute_lines": False,
            }
        )

        wizard.action_recompute()

        self.assertAlmostEqual(root.full_cost_multiplier, 2.0)
        self.assertAlmostEqual(productive_line.full_cost_amount, 0.0)
