# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Analytic Search Panel",
    "summary": "Adds an analytic plan search panel to analytic lines",
    "version": "18.0.1.1.0",
    "category": "Accounting/Analytic",
    "website": "https://github.com/OCA/account-analytic",
    "author": "Quim Rebull (Coopdevs), Odoo Community Association (OCA)",
    "maintainers": ["QuiJoQuim"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": [
        "account",
    ],
    "data": [
        "views/account_analytic_plan.xml",
        "views/account_analytic_line.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_analytic_searchpanel/static/src/views/"
            "analytic_plan_level_list_view.js",
        ],
        # Pivot views are lazy loaded
        "web.assets_backend_lazy": [
            "account_analytic_searchpanel/static/src/views/"
            "analytic_plan_level_pivot_view.*",
        ],
        "web.assets_tests": [
            "account_analytic_searchpanel/static/tests/tours/*.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
