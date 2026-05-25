from odoo import fields, models


class AccountAnalyticFullCostAnalysisWizard(models.TransientModel):
    _name = "account.analytic.full.cost.analysis.wizard"
    _description = "Open historical full-cost analysis"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    analysis_date = fields.Date(
        string="Analysis Date",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )

    def action_open_report(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_analytic_dynamic_full_cost."
            "action_account_analytic_full_cost_report"
        )
        action["domain"] = [
            ("company_id", "=", self.company_id.id),
            ("analysis_date", "=", self.analysis_date),
        ]
        action["context"] = {
            "search_default_group_account": 1,
            "default_company_id": self.company_id.id,
        }
        action["name"] = "%s - %s" % (action["name"], self.analysis_date)
        return action
