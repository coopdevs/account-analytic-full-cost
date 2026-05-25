from odoo import fields, models


class AccountAnalyticFullCostRecomputeWizard(models.TransientModel):
    _name = "account.analytic.full.cost.recompute.wizard"
    _description = "Recompute analytic full cost multipliers and amounts"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    recompute_lines = fields.Boolean(
        string="Recompute analytic lines",
        default=True,
        help=(
            "If enabled, all analytic lines of the selected company will be "
            "recomputed so that the 'Full Cost Amount' field is "
            "updated according to the new full cost multipliers."
        ),
    )

    def action_recompute(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        date_to = fields.Date.context_today(self)
        plans = self.env["account.analytic.plan"]
        plans.recompute_full_cost_multipliers(company=company, date_to=date_to)

        if self.recompute_lines:
            date_from = plans._get_full_cost_period_start(company, date_to)
            lines = self.env["account.analytic.line"].search(
                [
                    ("company_id", "=", company.id),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                ]
            )
            lines.recompute_full_cost_amount()

        return {"type": "ir.actions.act_window_close"}
