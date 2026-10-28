# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Analytic Dynamic Full Cost",
    "summary": "Compute and store dynamic full cost in analytic lines",
    "version": "18.0.1.1.0",
    "category": "Accounting/Analytic",
    "author": "Quim Rebull (Coopdevs), Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/account-analytic",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["QuiJoQuim"],
    "depends": [
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/full_cost_security.xml",
        "views/analytic_plan_views.xml",
        "views/account_analytic_line_views.xml",
        "wizard/analytic_full_cost_recompute_wizard.xml",
        "views/res_config_settings_views.xml",
        "wizard/full_cost_analysis_wizard.xml",
        "views/full_cost_report_views.xml",
        "data/analytic_full_cost_cron.xml",
    ],
    "demo": [
        "demo/res_company_demo.xml",
        "demo/analytic_plan_demo.xml",
        "demo/analytic_account_demo.xml",
        "demo/analytic_line_demo.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
