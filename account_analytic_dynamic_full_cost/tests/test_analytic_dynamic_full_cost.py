# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.service.model import get_public_method
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticDynamicFullCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Work on a dedicated company so that demo data (or any other data of
        # the database) does not alter the plan weights.
        cls.company = cls.env["res.company"].create({"name": "Full Cost Company"})
        cls.env.user.company_ids |= cls.company
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                allowed_company_ids=[cls.company.id],
                tracking_disable=True,
            )
        )
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

    def test_multipliers_are_computed_per_company(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        root = self._create_plan("Multi Company Root")
        productive = self._create_plan("Multi Company Productive", parent=root)
        overhead = self._create_plan(
            "Multi Company Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account(
            "Multi Company Productive", productive
        )
        overhead_account = self._create_account("Multi Company Overhead", overhead)
        line = self._create_line("Company productive", productive_account, -100.0)
        self._create_line("Company overhead", overhead_account, -100.0)

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        self.Plan._recompute_full_cost_multipliers(
            company=other_company,
            date_to=self.reference_date,
        )
        line.recompute_full_cost_amount()

        self.assertAlmostEqual(productive.full_cost_multiplier, 2.0)
        self.assertAlmostEqual(
            productive.with_company(other_company).full_cost_multiplier, 1.0
        )
        self.assertAlmostEqual(line.full_cost_amount, -200.0)

    def test_new_line_uses_current_multiplier(self):
        root = self._create_plan("Create Root")
        productive = self._create_plan("Create Productive", parent=root)
        overhead = self._create_plan(
            "Create Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account("Create Productive", productive)
        overhead_account = self._create_account("Create Overhead", overhead)
        self._create_line("Create productive", productive_account, -100.0)
        self._create_line("Create overhead", overhead_account, -50.0)
        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )

        new_line = self._create_line("New productive", productive_account, -10.0)
        self.assertAlmostEqual(new_line.full_cost_amount, -15.0)
        self.assertAlmostEqual(new_line.full_cost_multiplier_snapshot, 1.5)

        new_line.amount = -20.0
        self.assertAlmostEqual(new_line.full_cost_amount, -30.0)

        new_line.write({root._column_name(): overhead_account.id})
        self.assertEqual(new_line.full_cost_role, "reproductive")
        self.assertAlmostEqual(new_line.full_cost_amount, 0.0)

    def test_plan_role_change_updates_line_role(self):
        root = self._create_plan("Role Change Root")
        child = self._create_plan("Role Change Child", parent=root)
        line = self._create_line(
            "Role change line", self._create_account("Role Change", child), -10.0
        )
        self.assertEqual(line.full_cost_role, "productive")

        root.full_cost_role = "not_analyzed"
        self.assertEqual(line.full_cost_role, "not_analyzed")

        root.full_cost_role = "productive"
        child.full_cost_role = "reproductive"
        self.assertEqual(line.full_cost_role, "reproductive")

    def test_zero_productive_weight_uses_neutral_multiplier(self):
        root = self._create_plan("Zero Weight Root")
        productive = self._create_plan("Zero Weight Productive", parent=root)
        overhead = self._create_plan(
            "Zero Weight Overhead", full_cost_role="reproductive", parent=root
        )
        overhead_account = self._create_account("Zero Weight Overhead", overhead)
        overhead_line = self._create_line("Overhead only", overhead_account, -100.0)

        self.Plan._recompute_full_cost_multipliers(
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

        self.Plan._recompute_full_cost_multipliers(
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

        self.Plan._recompute_full_cost_multipliers(
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

        report = self.Report.with_context(
            full_cost_analysis_date=self.reference_date
        ).search([("company_id", "=", self.company.id)])
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
        self.assertEqual(action["domain"], [("company_id", "=", self.company.id)])
        report_line = (
            self.Report.with_context(**action["context"])
            .search(action["domain"])
            .filtered(lambda item: item.line_id == productive_line)
        )
        self.assertEqual(report_line.analysis_date, self.reference_date)
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
        report_line = self.Report.with_context(
            full_cost_analysis_date=self.reference_date
        ).search([("line_id", "=", may_line.id)])

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

        self.Plan._recompute_full_cost_multipliers(
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

        self.Plan._recompute_full_cost_multipliers(
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

        self.Plan._recompute_full_cost_multipliers(
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
        productive_expense = self._create_line(
            "Productive expense", productive_account, -1000.0
        )
        overhead_revenue = self._create_line(
            "Overhead revenue", overhead_account, 20.0
        )
        overhead_expense = self._create_line(
            "Overhead expense", overhead_account, -120.0
        )

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        lines = (
            productive_revenue
            + productive_expense
            + overhead_revenue
            + overhead_expense
        )
        lines.recompute_full_cost_amount()

        # The net overhead cost (100) is half of the productive revenue (200):
        # the revenue carries it, the expenses are left untouched
        self.assertAlmostEqual(root.full_cost_multiplier, 0.5)
        self.assertAlmostEqual(productive.full_cost_multiplier, 0.5)
        self.assertAlmostEqual(overhead.full_cost_multiplier, 0.0)
        self.assertAlmostEqual(productive_revenue.full_cost_amount, 100.0)
        self.assertAlmostEqual(productive_expense.full_cost_amount, -1000.0)
        self.assertAlmostEqual(overhead_revenue.full_cost_amount, 0.0)
        self.assertAlmostEqual(overhead_expense.full_cost_amount, 0.0)
        self.assertAlmostEqual(
            sum(lines.mapped("full_cost_amount")), sum(lines.mapped("amount"))
        )

    def test_revenue_is_spread_proportionally_to_billing(self):
        self.company.full_cost_weight_basis = "revenue"
        root = self._create_plan("Billing Root")
        big = self._create_plan("Billing Big", parent=root)
        small = self._create_plan("Billing Small", parent=root)
        overhead = self._create_plan(
            "Billing Overhead", full_cost_role="reproductive", parent=root
        )
        big_line = self._create_line(
            "Big billing", self._create_account("Billing Big", big), 1000.0
        )
        small_line = self._create_line(
            "Small billing", self._create_account("Billing Small", small), 100.0
        )
        self._create_line(
            "Overhead", self._create_account("Billing Overhead", overhead), -110.0
        )

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        (big_line + small_line).recompute_full_cost_amount()

        # Billing ten times more bears ten times more overhead
        self.assertAlmostEqual(big_line.full_cost_amount, 900.0)
        self.assertAlmostEqual(small_line.full_cost_amount, 90.0)

    def test_reproductive_net_balance_is_spread(self):
        root = self._create_plan("Net Balance Root")
        productive = self._create_plan("Net Balance Productive", parent=root)
        overhead = self._create_plan(
            "Net Balance Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account(
            "Net Balance Productive", productive
        )
        overhead_account = self._create_account("Net Balance Overhead", overhead)
        lines = (
            self._create_line("Productive cost", productive_account, -200.0)
            + self._create_line("Productive revenue", productive_account, 300.0)
            + self._create_line("Overhead cost", overhead_account, -150.0)
            + self._create_line("Overhead revenue", overhead_account, 50.0)
        )

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        lines.recompute_full_cost_amount()

        # Net overhead cost: 150 - 50 = 100, spread over 200 of expenses
        self.assertAlmostEqual(productive.full_cost_multiplier, 1.5)
        self.assertEqual(
            lines.mapped("full_cost_amount"), [-300.0, 300.0, 0.0, 0.0]
        )
        self.assertAlmostEqual(
            sum(lines.mapped("full_cost_amount")), sum(lines.mapped("amount"))
        )

    def test_cost_without_base_lines_goes_up_one_level(self):
        root = self._create_plan("Push Up Root")
        worked = self._create_plan("Push Up Worked", parent=root)
        empty = self._create_plan("Push Up Empty", parent=root)
        empty_overhead = self._create_plan(
            "Push Up Empty Overhead", full_cost_role="reproductive", parent=empty
        )
        worked_line = self._create_line(
            "Worked cost", self._create_account("Push Up Worked", worked), -100.0
        )
        overhead_line = self._create_line(
            "Orphan overhead",
            self._create_account("Push Up Empty Overhead", empty_overhead),
            -40.0,
        )

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        (worked_line + overhead_line).recompute_full_cost_amount()

        # The empty plan has no expenses to carry its overhead, so the root
        # level spreads it over the rest of the plans
        self.assertAlmostEqual(worked.full_cost_multiplier, 1.4)
        self.assertAlmostEqual(worked_line.full_cost_amount, -140.0)
        self.assertAlmostEqual(overhead_line.full_cost_amount, 0.0)

    def test_root_overhead_is_spread_over_productive_expenses_only(self):
        root = self._create_plan("Levels Root")
        loaded = self._create_plan("Levels Loaded", parent=root)
        loaded_overhead = self._create_plan(
            "Levels Loaded Overhead", full_cost_role="reproductive", parent=loaded
        )
        plain = self._create_plan("Levels Plain", parent=root)
        structure = self._create_plan(
            "Levels Structure", full_cost_role="reproductive", parent=root
        )
        lines = (
            self._create_line(
                "Loaded cost", self._create_account("Levels Loaded", loaded), -100.0
            )
            + self._create_line(
                "Loaded overhead",
                self._create_account("Levels Loaded Overhead", loaded_overhead),
                -100.0,
            )
            + self._create_line(
                "Plain cost", self._create_account("Levels Plain", plain), -100.0
            )
            + self._create_line(
                "Structure",
                self._create_account("Levels Structure", structure),
                -100.0,
            )
        )

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        lines.recompute_full_cost_amount()

        # The structure goes half and half (same productive expenses), and the
        # loaded plan also carries its own overhead
        self.assertAlmostEqual(loaded.full_cost_multiplier, 2.5)
        self.assertAlmostEqual(plain.full_cost_multiplier, 1.5)
        self.assertEqual(
            lines.mapped("full_cost_amount"), [-250.0, 0.0, -150.0, 0.0]
        )
        self.assertAlmostEqual(
            sum(lines.mapped("full_cost_amount")), sum(lines.mapped("amount"))
        )

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

        self.company.write(
            {
                "full_cost_period": "fiscal_year",
                "fiscalyear_last_month": "12",
                "fiscalyear_last_day": 31,
            }
        )
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2025, 1, 1),
        )

        self.company.write({"fiscalyear_last_month": "6", "fiscalyear_last_day": 30})
        self.assertEqual(
            self.Plan._get_full_cost_period_start(self.company, self.reference_date),
            date(2024, 7, 1),
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
            inside_line._get_analytic_accounts(),
            -10.0,
            line_date=date(2000, 1, 1),
        )

        window_lines = self.Line.search([("is_in_full_cost_window", "=", True)])
        outside_lines = self.Line.search([("is_in_full_cost_window", "=", False)])

        self.assertIn(inside_line, window_lines)
        self.assertNotIn(outside_line, window_lines)
        self.assertIn(outside_line, outside_lines)
        self.assertNotIn(inside_line, outside_lines)
        self.assertTrue(inside_line.is_in_full_cost_window)
        self.assertFalse(outside_line.is_in_full_cost_window)

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
        # The line keeps the amount computed at creation time
        self.assertAlmostEqual(productive_line.full_cost_amount, -100.0)

    def test_parent_cannot_become_reproductive_with_productive_children(self):
        root = self._create_plan("Constraint Root")
        self._create_plan("Constraint Productive Child", parent=root)

        with self.assertRaises(ValidationError):
            root.full_cost_role = "reproductive"

    def test_historical_report_matches_stored_full_cost(self):
        root = self._create_plan("Deep Root")
        line_a = self._create_plan("Deep Line A", parent=root)
        line_a_projects = self._create_plan("Deep A Projects", parent=line_a)
        line_a_overhead = self._create_plan(
            "Deep A Overhead", full_cost_role="reproductive", parent=line_a
        )
        structure = self._create_plan(
            "Deep Structure", full_cost_role="reproductive", parent=root
        )
        tags = self._create_plan("Deep Tags", full_cost_role="not_analyzed")
        tag = self._create_plan("Deep Tag", parent=tags)

        accounts = {
            plan: self._create_account(plan.name, plan)
            for plan in (line_a, line_a_projects, line_a_overhead, structure, tag)
        }
        lines = (
            self._create_line("A direct", accounts[line_a], -50.0)
            + self._create_multidimensional_line(
                "A project with tag",
                accounts[line_a_projects] + accounts[tag],
                -100.0,
            )
            + self._create_line("A overhead", accounts[line_a_overhead], -50.0)
            + self._create_line("Structure", accounts[structure], -75.0)
            + self._create_line("Tag only", accounts[tag], -30.0)
            + self._create_line("Revenue", accounts[line_a_projects], 500.0)
        )

        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        lines.recompute_full_cost_amount()
        report = self.Report.with_context(
            full_cost_analysis_date=self.reference_date
        ).search([("line_id", "in", lines.ids)])

        # The rates of the levels add up: root 75 / 150, line A 50 / 150
        self.assertAlmostEqual(root.full_cost_multiplier, 1.5)
        self.assertAlmostEqual(line_a.full_cost_multiplier, 1.5 + 1 / 3)
        self.assertAlmostEqual(line_a_projects.full_cost_multiplier, 1.5 + 1 / 3)
        self.assertEqual(len(report), len(lines))
        for report_line in report:
            line = report_line.line_id
            self.assertEqual(report_line.full_cost_role, line.full_cost_role)
            self.assertAlmostEqual(
                report_line.full_cost_amount, line.full_cost_amount
            )
            self.assertAlmostEqual(
                report_line.full_cost_multiplier,
                line.full_cost_multiplier_snapshot,
                places=5,
            )
        # Every cost of the analysed dimension ends up in productive lines
        analysed = lines.filtered(lambda line: line.full_cost_role != "not_analyzed")
        self.assertAlmostEqual(
            sum(analysed.filtered(lambda line: line.amount < 0).mapped(
                "full_cost_amount"
            )),
            -275.0,
        )

    def test_settings_are_stored_on_the_company(self):
        settings = self.env["res.config.settings"].create(
            {
                "full_cost_period": "fiscal_year",
                "full_cost_weight_basis": "revenue",
            }
        )
        settings.execute()

        self.assertEqual(self.company.full_cost_period, "fiscal_year")
        self.assertEqual(self.company.full_cost_weight_basis, "revenue")

    def test_multipliers_cannot_be_recomputed_through_rpc(self):
        with self.assertRaises(AttributeError):
            get_public_method(self.Plan, "recompute_full_cost_multipliers")
        with self.assertRaises(AccessError):
            get_public_method(self.Plan, "_recompute_full_cost_multipliers")

    def test_full_cost_cannot_be_written_directly(self):
        root = self._create_plan("Forged Root")
        productive = self._create_plan("Forged Productive", parent=root)
        overhead = self._create_plan(
            "Forged Overhead", full_cost_role="reproductive", parent=root
        )
        productive_account = self._create_account("Forged Productive", productive)
        self._create_line(
            "Forged overhead", self._create_account("Forged Overhead", overhead), -50.0
        )
        self._create_line("Forged base", productive_account, -100.0)
        self.Plan._recompute_full_cost_multipliers(
            company=self.company,
            date_to=self.reference_date,
        )
        line = self.Line.create(
            {
                "name": "Forged line",
                "date": self.reference_date,
                "company_id": self.company.id,
                root._column_name(): productive_account.id,
                "amount": -10.0,
                "full_cost_amount": -999.0,
            }
        )
        self.assertAlmostEqual(line.full_cost_amount, -15.0)

        line.write({"full_cost_amount": -999.0, "full_cost_multiplier_snapshot": 9.0})

        self.assertAlmostEqual(line.full_cost_amount, -15.0)
        self.assertAlmostEqual(line.full_cost_multiplier_snapshot, 1.5)

    def test_historical_report_respects_analytic_line_rules(self):
        root = self._create_plan("Restricted Root")
        productive = self._create_plan("Restricted Productive", parent=root)
        overhead = self._create_plan(
            "Restricted Overhead", full_cost_role="reproductive", parent=root
        )
        visible_line = self._create_line(
            "Visible productive",
            self._create_account("Restricted Productive", productive),
            -100.0,
        )
        hidden_line = self._create_line(
            "Hidden overhead",
            self._create_account("Restricted Overhead", overhead),
            -50.0,
        )
        restricted_group = self.env["res.groups"].create(
            {"name": "Restricted analytic lines"}
        )
        self.env["ir.rule"].create(
            {
                "name": "Hide some analytic lines",
                "model_id": self.env["ir.model"]._get_id("account.analytic.line"),
                "groups": [(4, restricted_group.id)],
                "domain_force": "[('name', '!=', 'Hidden overhead')]",
            }
        )
        user = self.env["res.users"].create(
            {
                "name": "Restricted analytic user",
                "login": "restricted_analytic_user",
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
                "groups_id": [
                    # No accounting group: their rules would show every line
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("analytic.group_analytic_accounting").id),
                    (4, restricted_group.id),
                ],
            }
        )
        report = self.Report.with_user(user).with_context(
            full_cost_analysis_date=self.reference_date
        )

        report_lines = report.search([("company_id", "=", self.company.id)])

        self.assertIn(visible_line.id, report_lines.mapped("line_id").ids)
        self.assertNotIn(hidden_line.id, report_lines.mapped("line_id").ids)
        self.assertFalse(report.browse(hidden_line.id).exists())
        # The hidden line still weights the multipliers
        visible = report_lines.filtered(lambda item: item.line_id == visible_line)
        self.assertAlmostEqual(visible.full_cost_amount, -150.0)
