from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    analytic_report_personnel_cost = fields.Selection(
        [
            ("accounting", "Accounting"),
            ("timesheets", "Timesheets"),
            ("all", "All analytic lines"),
        ],
        string="Analytic Personnel Cost Source",
        required=True,
        default="accounting",
        help="When the personnel cost reaches the analytic accounting both "
        "through the payroll entries and the valued timesheets, the analytic "
        "reports must count only one of them.\n\n"
        "- Accounting: analytic lines without financial account, such as the "
        "timesheets, are ignored.\n"
        "- Timesheets: analytic lines of the personnel accounts are ignored, "
        "the timesheets carry the personnel cost.\n"
        "- All analytic lines: nothing is ignored.",
    )
    analytic_report_personnel_account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="res_company_analytic_report_personnel_account_rel",
        string="Analytic Personnel Accounts",
        help="Financial accounts of the personnel cost, ignored by the analytic "
        "reports when the timesheets carry the personnel cost.",
    )
