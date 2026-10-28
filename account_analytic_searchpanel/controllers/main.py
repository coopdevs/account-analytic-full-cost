# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import json
from collections import deque

from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import UnprocessableEntity

from odoo import fields, http
from odoo.http import content_disposition, request
from odoo.tools import osutil
from odoo.tools.misc import format_date, format_datetime, xlsxwriter

# Solid version of the shades of the plan level rows on the screen (the
# rgb(1, 126, 132) teal over white, with the alpha of each level)
PLAN_LEVEL_FILLS = {
    1: "#B3D8DA",
    2: "#D4E9EA",
    3: "#EBF5F5",
    4: "#F5FAFA",
}
HEADER_FILL = "#E9ECEF"
TITLE_COLOR = "#01666B"
BORDER_COLOR = "#D9D9D9"


def _is_plan_field(fname):
    return bool(fname) and (
        fname == "analytic_plan_id" or fname.startswith("analytic_plan_level_")
    )


class AnalyticPivotExporter(http.Controller):
    """Spreadsheet export of the analytic pivots: the table as the standard
    pivot export writes it, below a block with its context, and with the plan
    level rows shaded as on the screen."""

    @http.route(
        "/account_analytic_searchpanel/pivot/export_xlsx",
        type="http",
        auth="user",
        readonly=True,
    )
    def export_xlsx(self, data, **kw):
        jdata = json.load(data) if isinstance(data, FileStorage) else json.loads(data)
        if not jdata:
            raise UnprocessableEntity(request.env._("No data to export"))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet(jdata["title"][:31])
        formats = _Formats(workbook)
        y = self._write_info(worksheet, formats, jdata)
        self._write_table(worksheet, formats, jdata, y + 1)
        workbook.close()
        filename = osutil.clean_filename(
            "{} {}".format(jdata["title"], fields.Date.context_today(request.env.user))
        )
        return request.make_response(
            output.getvalue(),
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("Content-Disposition", content_disposition(filename + ".xlsx")),
            ],
        )

    def _get_export_info(self, jdata):
        """[(label, value)] saying who exported the table, when, and what it
        covers."""
        env = request.env
        return [
            (
                env._("Exported"),
                f"{env.user.name}, {format_datetime(env, fields.Datetime.now())}",
            ),
            (env._("Analytic plans"), self._get_export_plans(jdata)),
            (env._("Period"), self._get_export_period(jdata)),
        ]

    def _get_export_records(self, jdata):
        """The exported model, restricted to the domain of the table, or None
        when it cannot be read."""
        model = jdata.get("model")
        if model not in request.env:
            return None
        domain = (jdata.get("export_info") or {}).get("domain") or []
        return request.env[model].with_context(active_test=False), domain

    def _get_export_plans(self, jdata):
        """The analytic plans the table is filtered on, from the search panel
        and the search facets."""
        info = jdata.get("export_info") or {}
        names = [
            selection["name"]
            for selection in info.get("panel", [])
            if _is_plan_field(selection.get("field"))
        ]
        for facet in info.get("facets", []):
            if _is_plan_field(facet.get("field")):
                names += facet.get("values", [])
        return ", ".join(names) or request.env._("All")

    def _get_export_period(self, jdata):
        """First and last date of the exported data."""
        records = self._get_export_records(jdata)
        if not records or "date" not in records[0]._fields:
            return ""
        model, domain = records
        [(date_from, date_to)] = model._read_group(
            domain, aggregates=["date:min", "date:max"]
        )
        if not date_from:
            return ""
        env = request.env
        return f"{format_date(env, date_from)} - {format_date(env, date_to)}"

    def _write_info(self, worksheet, formats, jdata):
        """Write the title and the context of the table, return the next row."""
        worksheet.write(0, 0, jdata["title"], formats.get(title=True))
        y = 1
        for label, value in self._get_export_info(jdata):
            worksheet.write(y, 0, label, formats.get(label=True))
            worksheet.write(y, 1, value or "")
            y += 1
        return y + 1

    def _write_table(self, worksheet, formats, jdata, y0):
        """Same layout as the standard pivot export, from row ``y0``."""
        measure_count = min(jdata["measure_count"], 100000)
        origin_count = min(jdata["origin_count"], 100000)
        header = formats.get(header=True)
        header_bold = formats.get(header=True, bold=True)
        span = measure_count * (2 * origin_count - 1)

        # Column group headers
        x, y, carry = 1, y0, deque()
        for header_row in jdata["col_group_headers"]:
            worksheet.write(y, 0, "", header)
            for cell in header_row:
                while carry and carry[0]["x"] == x:
                    pending = carry.popleft()
                    for j in range(span):
                        worksheet.write(y, x + j, "", header)
                    if pending["height"] > 1:
                        carry.append({"x": x, "height": pending["height"] - 1})
                    x += span
                width = min(cell["width"], 100000)
                for j in range(width):
                    worksheet.write(y, x + j, cell["title"] if j == 0 else "", header)
                if cell["height"] > 1:
                    carry.append({"x": x, "height": cell["height"] - 1})
                x += width
            while carry and carry[0]["x"] == x:
                pending = carry.popleft()
                for j in range(span):
                    worksheet.write(y, x + j, "", header)
                if pending["height"] > 1:
                    carry.append({"x": x, "height": pending["height"] - 1})
                x += span
            x, y = 1, y + 1

        # Measure and origin headers
        for key, step in (("measure_headers", 2 * origin_count - 1), ("origin_headers", 1)):
            cells = jdata.get(key) or []
            if not cells:
                continue
            worksheet.write(y, 0, "", header)
            for cell in cells:
                worksheet.write(y, x, cell["title"], header_bold if cell["is_bold"] else header)
                for i in range(1, step):
                    worksheet.write(y, x + i, "", header)
                x += step
            x, y = 1, y + 1

        # Data, shaded by plan level
        first_data_row = y
        for row in jdata["rows"]:
            level = row.get("analytic_level") or 0
            total = not row["indent"]
            worksheet.write(
                y,
                0,
                row["title"],
                formats.get(level=level, bold=total or level == 1, indent=row["indent"]),
            )
            for x, cell in enumerate(row["values"], start=1):
                worksheet.write(
                    y,
                    x,
                    cell["value"],
                    formats.get(
                        level=level,
                        bold=total or cell.get("is_bold", False) or level == 1,
                        number=True,
                    ),
                )
            y += 1

        worksheet.set_column(0, 0, 45)
        worksheet.set_column(1, max(len(jdata["rows"][0]["values"]) if jdata["rows"] else 1, 1), 15)
        worksheet.freeze_panes(first_data_row, 1)


class _Formats:
    """Cache of the cell formats of the export, by their properties."""

    def __init__(self, workbook):
        self.workbook = workbook
        self.cache = {}

    def get(self, level=0, bold=False, number=False, indent=0, header=False,
            title=False, label=False):
        key = (level, bold, number, indent, header, title, label)
        if key not in self.cache:
            properties = {}
            if title:
                properties.update(bold=True, font_size=14, font_color=TITLE_COLOR)
            elif label:
                properties.update(bold=True, font_color="#434343")
            else:
                properties.update(border=1, border_color=BORDER_COLOR)
                if header:
                    properties.update(bg_color=HEADER_FILL, pattern=1)
                elif level in PLAN_LEVEL_FILLS:
                    properties.update(bg_color=PLAN_LEVEL_FILLS[level], pattern=1)
                if bold:
                    properties["bold"] = True
                if number:
                    properties["num_format"] = "#,##0.00"
                if indent:
                    properties["indent"] = indent
            self.cache[key] = self.workbook.add_format(properties)
        return self.cache[key]
