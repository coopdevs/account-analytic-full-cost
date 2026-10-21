# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountAnalyticFullCostRecomputeWizard(models.TransientModel):
    _name = "account.analytic.full.cost.recompute.wizard"
    _description = "Recompute analytic full cost multipliers and amounts"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    recompute_lines = fields.Boolean(
        string="Recompute analytic lines",
        default=True,
        help=(
            "If enabled, the analytic lines of the selected company inside the "
            "current full-cost window are recomputed so that their 'Full Cost "
            "Amount' is updated according to the new full cost multipliers."
        ),
    )

    def action_recompute(self):
        self.ensure_one()
        self.env["account.analytic.plan"].with_company(
            self.company_id
        )._recompute_full_cost(self.company_id, recompute_lines=self.recompute_lines)
        return {"type": "ir.actions.act_window_close"}
