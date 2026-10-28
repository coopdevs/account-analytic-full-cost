from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    analytic_report_personnel_cost = fields.Selection(
        related="company_id.analytic_report_personnel_cost",
        readonly=False,
    )
    analytic_report_personnel_account_ids = fields.Many2many(
        related="company_id.analytic_report_personnel_account_ids",
        readonly=False,
    )
