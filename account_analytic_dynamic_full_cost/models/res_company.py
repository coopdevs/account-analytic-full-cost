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
            "N days, where N is defined in the 'Full Cost Window (Days)' field."
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
            "Defines which analytic line amounts are used as plan weights when "
            "computing full cost multipliers.\n\n"
            "- Expenses: negative analytic amounts are used as positive "
            "expense weight.\n"
            "- Revenue: positive analytic amounts are used as revenue weight."
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
