# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import json
import zipfile
from datetime import date

from odoo import http
from odoo.tests import HttpCase, tagged

EXPORT_URL = "/account_analytic_searchpanel/pivot/export_xlsx"


def export_table(model, export_info=None):
    """A table as the analytic pivot sends it: a plan of level 1, one of its
    accounts and the total."""
    return {
        "model": model,
        "title": "Monthly Analytics",
        "col_group_headers": [[{"title": "Total", "width": 1, "height": 1}]],
        "measure_headers": [{"title": "Amount", "width": 1, "height": 1, "is_bold": True}],
        "origin_headers": [],
        "measure_count": 1,
        "origin_count": 1,
        "rows": [
            {"title": "Total", "indent": 0, "analytic_level": 0,
             "values": [{"value": -50.0, "is_bold": True}]},
            {"title": "Project / Export Plan", "indent": 1, "analytic_level": 1,
             "values": [{"value": -50.0, "is_bold": False}]},
            {"title": "Export Account", "indent": 2, "analytic_level": 0,
             "values": [{"value": -50.0, "is_bold": False}]},
        ],
        "export_info": export_info or {
            "domain": [],
            "facets": [{"field": "analytic_plan_level_1_id", "values": ["Export Plan"]}],
            "panel": [{"field": "analytic_plan_id", "id": 1, "name": "Project"}],
        },
    }


class PivotExportCase(HttpCase):
    def export(self, table):
        self.authenticate("admin", "admin")
        response = self.url_open(
            EXPORT_URL,
            data={"data": json.dumps(table), "csrf_token": http.Request.csrf_token(self)},
        )
        self.assertEqual(response.status_code, 200, response.text[:500])
        workbook = zipfile.ZipFile(io.BytesIO(response.content))
        strings = workbook.read("xl/sharedStrings.xml").decode()
        styles = workbook.read("xl/styles.xml").decode()
        return strings, styles


@tagged("post_install", "-at_install")
class TestPivotExport(PivotExportCase):
    def test_export_has_context_and_colors(self):
        Plan = self.env["account.analytic.plan"]
        root, _other_plans = Plan._get_all_plans()
        account = self.env["account.analytic.account"].create(
            {"name": "Export Account", "plan_id": root.id}
        )
        self.env["account.analytic.line"].create(
            [
                {"name": "Export", "account_id": account.id, "amount": -10.0,
                 "date": date(2026, 2, 3)},
                {"name": "Export", "account_id": account.id, "amount": -40.0,
                 "date": date(2026, 9, 28)},
            ]
        )
        table = export_table("account.analytic.line")
        table["export_info"]["domain"] = [("name", "=", "Export")]
        strings, styles = self.export(table)

        for text in (
            "Monthly Analytics",
            "Exported",
            "Mitchell Admin, ",
            "Analytic plans",
            "Project, Export Plan",
            "Period",
            "02/03/2026 - 09/28/2026",
            "Project / Export Plan",
            "Export Account",
        ):
            self.assertIn(text, strings)
        # Nothing else: groupings and measures are not part of it
        self.assertNotIn("Measures", strings)
        # The level 1 plan row is shaded as on the screen
        self.assertIn("B3D8DA", styles)

    def test_no_plan_filter_means_all_plans(self):
        table = export_table(
            "account.analytic.line", {"domain": [], "facets": [], "panel": []}
        )
        strings, _styles = self.export(table)

        self.assertIn("All", strings)
