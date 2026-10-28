# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Analytic Dashboard",
    "summary": "Monthly revenue and expenses of the analytic plan hierarchy",
    "version": "18.0.1.0.0",
    "category": "Accounting/Analytic",
    "website": "https://github.com/OCA/account-analytic",
    "author": "Quim Rebull (Coopdevs), Odoo Community Association (OCA)",
    "maintainers": ["QuiJoQuim"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": [
        "account_analytic_searchpanel",
        "spreadsheet_dashboard",
    ],
    "data": [
        "views/analytic_monthly_report.xml",
        "views/res_config_settings_views.xml",
        "data/dashboards.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "account_analytic_dashboard/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "application": False,
}
