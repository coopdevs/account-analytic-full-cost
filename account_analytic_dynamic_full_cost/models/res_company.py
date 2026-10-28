# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    full_cost_period = fields.Selection(
        [
            ("biannual", "Two-year window"),
            ("annual", "Annual window"),
            ("triannual", "Three-year window"),
            ("monthly", "Monthly window"),
            ("rolling", "Rolling window (last N days)"),
            ("fiscal_year", "Current fiscal year"),
        ],
        string="Full Cost Period",
        required=True,
        default="biannual",
        help=(
            "Defines the period used to compute the full cost multiplier for "
            "each analytic plan.\n\n"
            "- Two-year window: uses imputations from the same day two years "
            "before the reference date.\n"
            "- Annual window: uses imputations from the same day of the "
            "previous year up to the reference date.\n"
            "- Three-year window: uses imputations from the same day three "
            "years before the reference date.\n"
            "- Monthly window: uses imputations from the same day of the "
            "previous month up to the reference date.\n"
            "- Rolling window (last N days): uses only imputations in the last "
            "N days, where N is defined in the 'Full Cost Window (Days)' field.\n"
            "- Current fiscal year: uses imputations from the first day of the "
            "fiscal year of the reference date up to the reference date, so "
            "that the full cost of the lines of the year adds up to their "
            "amount."
        ),
    )

    full_cost_weight_basis = fields.Selection(
        [
            ("expenses", "Expenses"),
            ("revenue", "Revenue"),
        ],
        string="Full Cost Weight Basis",
        required=True,
        default="expenses",
        help=(
            "Defines the analytic lines that weight the productive plans and "
            "carry the cost of the reproductive ones.\n\n"
            "- Expenses: the reproductive cost is spread proportionally to the "
            "expenses of the productive plans and added to them.\n"
            "- Revenue: the reproductive cost is spread proportionally to the "
            "revenue of the productive plans and deducted from it."
        ),
    )

    full_cost_window_days = fields.Integer(
        string="Full Cost Window (Days)",
        default=365,
        help=(
            "Number of days to look back when computing the full cost "
            "multiplier, "
            "only used when the method is set to 'Rolling window'.\n\n"
            "For example, with 90 days the system will calculate the "
            "multiplier based on imputations in the last 90 days before the "
            "reference date."
        ),
    )
