from odoo import fields, models


class AccountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    show_in_analytic_searchpanel = fields.Boolean(
        string="Show in Analytic Search Panel",
        default=True,
        help=(
            "If enabled, analytic lines using this plan can be explored from "
            "the Analytic Items search panel."
        ),
    )

    def write(self, vals):
        result = super().write(vals)
        if "show_in_analytic_searchpanel" in vals:
            self.env["account.analytic.line"].search(
                [("account_id.plan_id", "in", self.ids)]
            )._compute_analytic_plan_id()
        return result
