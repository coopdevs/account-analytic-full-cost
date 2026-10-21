# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountAnalyticFullCostAnalysisWizard(models.TransientModel):
    _name = "account.analytic.full.cost.analysis.wizard"
    _description = "Open historical full-cost analysis"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    analysis_date = fields.Date(
        string="Analysis Date",
        required=True,
        default=fields.Date.context_today,
    )

    def action_open_report(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_analytic_dynamic_full_cost."
            "action_account_analytic_full_cost_report"
        )
        action["domain"] = [("company_id", "=", self.company_id.id)]
        action["context"] = {
            "full_cost_analysis_date": fields.Date.to_string(self.analysis_date),
            "search_default_group_account": 1,
        }
        action["name"] = self.env._(
            "Full-Cost Analysis at %(date)s",
            date=fields.Date.to_string(self.analysis_date),
        )
        return action
