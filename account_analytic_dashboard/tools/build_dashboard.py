"""Build ``data/files/analytic_dashboard.json``, the analytic spreadsheet
dashboard.

The dashboard is generated instead of hand edited, so that its layout can be
changed and regenerated. Run it from anywhere:

    python3 account_analytic_dashboard/tools/build_dashboard.py
"""

import json
from pathlib import Path

TARGET = Path(__file__).parent.parent / "data" / "files" / "analytic_dashboard.json"
MODEL = "account.analytic.line"
DOMAIN = [
    "&",
    ["analytic_plan_level_0_id", "!=", False],
    ["analytic_report_included", "=", True],
]
PERIOD_FILTER = "a1b2c3d4-0001-4a6e-9a51-6e7d0a7a0001"
LINE_FILTER = "a1b2c3d4-0002-4a6e-9a51-6e7d0a7a0002"
LEVEL_1 = "analytic_plan_level_1_id"
MONTH = "#date:month"
MONTHS = 12
LINES = 15
TOP = 10
MENU = "account_analytic_dashboard.menu_analytic_monthly_report"
# Opened to see the records of a cell: its views are the analytic ones
ACTION = "account_analytic_dashboard.action_analytic_monthly_report"

FIELD_MATCHING = {
    PERIOD_FILTER: {"chain": "date", "type": "date", "offset": 0},
    LINE_FILTER: {"chain": LEVEL_1, "type": "many2one"},
}
STYLES = {
    "title": 1,
    "header": 2,
    "total": 3,
}
FORMATS = {"amount": 1, "percent": 2}


def col(index):
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[index]


def text(value):
    return {"content": f'=_t("{value}")'}


def formula(value):
    return {"content": f"={value}"}


def header(value):
    """Pivot header, empty instead of an error out of the pivot range."""
    return formula(f'IFERROR({value},"")')


def guarded(condition_cells, value):
    """Value left empty when one of the given header cells is empty."""
    conditions = ",".join(f'{cell}=""' for cell in condition_cells)
    return formula(f'IF(OR({conditions}),"",{value})')


def pivot(pivot_id, name, rows=(), columns=(), measures=(), sorted_by=None):
    definition = {
        "type": "ODOO",
        "id": str(pivot_id),
        "formulaId": str(pivot_id),
        "name": name,
        "model": MODEL,
        "domain": DOMAIN,
        "context": {},
        "rows": list(rows),
        "columns": list(columns),
        "measures": [{"id": m, "fieldName": m} for m in measures],
        "fieldMatching": FIELD_MATCHING,
        "actionXmlId": ACTION,
    }
    if sorted_by:
        measure, order = sorted_by
        definition["sortedColumn"] = {
            "groupId": [[], []],
            "measure": measure,
            "order": order,
        }
    return definition


def scorecard(figure_id, x, title, key_cell):
    return {
        "id": figure_id,
        "x": x,
        "y": 11,
        "width": 220,
        "height": 109,
        "tag": "chart",
        "data": {
            "type": "scorecard",
            "title": {"text": title, "color": "#434343", "bold": True},
            "keyValue": key_cell,
            "baselineMode": "text",
            "baselineDescr": "",
            "background": "#FFFFFF",
            "humanize": False,
        },
    }


def result_conditional_formats(ranges, prefix):
    return [
        {
            "id": f"{prefix}-positive",
            "ranges": ranges,
            "rule": {
                "type": "CellIsRule",
                "operator": "GreaterThan",
                "values": ["0"],
                "style": {"textColor": "#2E7D32"},
            },
        },
        {
            "id": f"{prefix}-negative",
            "ranges": ranges,
            "rule": {
                "type": "CellIsRule",
                "operator": "LessThan",
                "values": ["0"],
                "style": {"textColor": "#C62828"},
            },
        },
    ]


def build():
    month_row = {"fieldName": "date", "granularity": "month", "order": "asc"}
    level_1_row = {"fieldName": LEVEL_1}
    account_row = {"fieldName": "account_id"}
    pivots = {
        "1": pivot(1, "Totals", measures=("amount_revenue", "amount_expense", "amount")),
        "2": pivot(
            2,
            "By month",
            rows=[month_row],
            measures=("amount_revenue", "amount_expense", "amount"),
        ),
        "3": pivot(
            3,
            "By line",
            rows=[level_1_row],
            measures=("amount_revenue", "amount_expense", "amount"),
            sorted_by=("amount_revenue", "desc"),
        ),
        "4": pivot(
            4,
            "By line and month",
            rows=[level_1_row],
            columns=[month_row],
            measures=("amount",),
            sorted_by=("amount", "desc"),
        ),
        "5": pivot(
            5,
            "Top expenses",
            rows=[account_row],
            measures=("amount_expense",),
            sorted_by=("amount_expense", "asc"),
        ),
        "6": pivot(
            6,
            "Top revenue",
            rows=[account_row],
            measures=("amount_revenue",),
            sorted_by=("amount_revenue", "desc"),
        ),
    }

    # Data sheet: key figures and the monthly series of the chart
    data = {
        "A1": text("KPI - Revenue"),
        "B1": formula('PIVOT.VALUE(1,"amount_revenue")'),
        "C1": formula("FORMAT.LARGE.NUMBER(B1)"),
        "A2": text("KPI - Expenses"),
        "B2": formula('-PIVOT.VALUE(1,"amount_expense")'),
        "C2": formula("FORMAT.LARGE.NUMBER(B2)"),
        "A3": text("KPI - Result"),
        "B3": formula('PIVOT.VALUE(1,"amount")'),
        "C3": formula("FORMAT.LARGE.NUMBER(B3)"),
        "A4": text("KPI - Margin"),
        "B4": formula("IFERROR(B3/B1)"),
        "C4": formula("B4"),
        "A9": text("Month"),
        "B9": text("Revenue"),
        "C9": text("Expenses"),
        "D9": text("Result"),
    }
    for n in range(1, MONTHS + 1):
        row = 9 + n
        data[f"A{row}"] = header(f'PIVOT.HEADER(2,"{MONTH}",{n})')
        data[f"B{row}"] = guarded(
            [f"A{row}"], f'PIVOT.VALUE(2,"amount_revenue","{MONTH}",{n})'
        )
        data[f"C{row}"] = guarded(
            [f"A{row}"], f'-PIVOT.VALUE(2,"amount_expense","{MONTH}",{n})'
        )
        data[f"D{row}"] = guarded([f"A{row}"], f'PIVOT.VALUE(2,"amount","{MONTH}",{n})')
    last_month_row = 9 + MONTHS

    cells = {}
    styles = {}
    formats = {}
    borders = {}

    # Monthly chart
    cells["A7"] = text("Revenue and expenses by month")
    styles["A7"] = STYLES["title"]
    borders["A7:N7"] = 1

    # Result by line (level 1)
    top = 23
    cells[f"A{top}"] = text("Result by line")
    styles[f"A{top}"] = STYLES["title"]
    borders[f"A{top}:E{top}"] = 1
    header_row = top + 1
    for index, title in enumerate(("Line", "Revenue", "Expenses", "Result", "Margin")):
        cells[f"{col(index)}{header_row}"] = text(title)
    styles[f"A{header_row}:E{header_row}"] = STYLES["header"]
    first = header_row + 1
    for n in range(1, LINES + 1):
        row = header_row + n
        position = f'"#{LEVEL_1}",{n}'
        cells[f"A{row}"] = header(f"PIVOT.HEADER(3,{position})")
        cells[f"B{row}"] = guarded(
            [f"A{row}"], f'PIVOT.VALUE(3,"amount_revenue",{position})'
        )
        cells[f"C{row}"] = guarded(
            [f"A{row}"], f'-PIVOT.VALUE(3,"amount_expense",{position})'
        )
        cells[f"D{row}"] = guarded([f"A{row}"], f'PIVOT.VALUE(3,"amount",{position})')
        cells[f"E{row}"] = formula(f'IF(B{row}="","",IFERROR(D{row}/B{row},""))')
    last = header_row + LINES
    total = last + 1
    cells[f"A{total}"] = text("Total")
    cells[f"B{total}"] = formula('PIVOT.VALUE(3,"amount_revenue")')
    cells[f"C{total}"] = formula('-PIVOT.VALUE(3,"amount_expense")')
    cells[f"D{total}"] = formula('PIVOT.VALUE(3,"amount")')
    cells[f"E{total}"] = formula(f'IF(B{total},D{total}/B{total},"")')
    styles[f"A{total}:E{total}"] = STYLES["total"]
    borders[f"A{total}:E{total}"] = 2
    formats[f"B{first}:D{total}"] = FORMATS["amount"]
    formats[f"E{first}:E{total}"] = FORMATS["percent"]
    conditional_formats = result_conditional_formats([f"D{first}:D{total}"], "line")

    # Result by line and month
    top = total + 3
    cells[f"A{top}"] = text("Monthly result by line")
    styles[f"A{top}"] = STYLES["title"]
    borders[f"A{top}:N{top}"] = 1
    header_row = top + 1
    cells[f"A{header_row}"] = text("Line")
    cells[f"B{header_row}"] = text("Total")
    for n in range(1, MONTHS + 1):
        cells[f"{col(n + 1)}{header_row}"] = header(
            f'PIVOT.HEADER(4,"{MONTH}",{n})'
        )
    styles[f"A{header_row}:{col(MONTHS + 1)}{header_row}"] = STYLES["header"]
    first = header_row + 1
    for r in range(1, LINES + 1):
        row = header_row + r
        line = f'"#{LEVEL_1}",{r}'
        cells[f"A{row}"] = header(f"PIVOT.HEADER(4,{line})")
        cells[f"B{row}"] = guarded([f"$A{row}"], f'PIVOT.VALUE(4,"amount",{line})')
        for n in range(1, MONTHS + 1):
            cells[f"{col(n + 1)}{row}"] = guarded(
                [f"$A{row}", f"{col(n + 1)}${header_row}"],
                f'PIVOT.VALUE(4,"amount",{line},"{MONTH}",{n})',
            )
    total = header_row + LINES + 1
    cells[f"A{total}"] = text("Total")
    cells[f"B{total}"] = formula('PIVOT.VALUE(4,"amount")')
    for n in range(1, MONTHS + 1):
        cells[f"{col(n + 1)}{total}"] = guarded(
            [f"{col(n + 1)}${header_row}"], f'PIVOT.VALUE(4,"amount","{MONTH}",{n})'
        )
    styles[f"A{total}:{col(MONTHS + 1)}{total}"] = STYLES["total"]
    borders[f"A{total}:{col(MONTHS + 1)}{total}"] = 2
    grid = f"B{first}:{col(MONTHS + 1)}{total}"
    formats[grid] = FORMATS["amount"]
    conditional_formats += result_conditional_formats([grid], "month")

    # Top accounts
    top = total + 3
    for pivot_id, title, measure, sign in (
        (5, "Top expenses", "amount_expense", "-"),
        (6, "Top revenue", "amount_revenue", ""),
    ):
        name_col, value_col = "A", "B"
        cells[f"{name_col}{top}"] = text(title)
        styles[f"{name_col}{top}"] = STYLES["title"]
        borders[f"{name_col}{top}:C{top}"] = 1
        cells[f"{name_col}{top + 1}"] = text("Analytic account")
        cells[f"{value_col}{top + 1}"] = text("Amount")
        styles[f"{name_col}{top + 1}:{value_col}{top + 1}"] = STYLES["header"]
        for n in range(1, TOP + 1):
            row = top + 1 + n
            cells[f"{name_col}{row}"] = header(
                f'PIVOT.HEADER({pivot_id},"#account_id",{n})'
            )
            cells[f"{value_col}{row}"] = guarded(
                [f"{name_col}{row}"],
                f'{sign}PIVOT.VALUE({pivot_id},"{measure}","#account_id",{n})',
            )
        formats[f"{value_col}{top + 2}:{value_col}{top + 1 + TOP}"] = FORMATS["amount"]
        conditional_formats.append(
            {
                "id": f"top-{pivot_id}",
                "ranges": [f"{name_col}{top + 2}:{name_col}{top + 1 + TOP}"],
                "rule": {
                    "type": "DataBarRule",
                    "color": 16764356 if pivot_id == 5 else 13691120,
                    "rangeValues": f"{value_col}{top + 2}:{value_col}{top + 1 + TOP}",
                },
            }
        )
        top += TOP + 4
    last_row = top

    chart_id = "a1b2c3d4-1000-4a6e-9a51-6e7d0a7a1000"
    figures = [
        scorecard("a1b2c3d4-1001-4a6e-9a51-6e7d0a7a1001", 0, "Revenue", "Data!C1"),
        scorecard("a1b2c3d4-1002-4a6e-9a51-6e7d0a7a1002", 230, "Expenses", "Data!C2"),
        scorecard("a1b2c3d4-1003-4a6e-9a51-6e7d0a7a1003", 460, "Result", "Data!C3"),
        scorecard("a1b2c3d4-1004-4a6e-9a51-6e7d0a7a1004", 690, "Margin", "Data!C4"),
        {
            "id": chart_id,
            "x": 0,
            "y": 178,
            "width": 1100,
            "height": 345,
            "tag": "chart",
            "data": {
                "type": "combo",
                "title": {"text": ""},
                "background": "#FFFFFF",
                "legendPosition": "top",
                "dataSetsHaveTitle": True,
                "dataSets": [
                    {"dataRange": f"Data!B9:B{last_month_row}", "type": "bar"},
                    {"dataRange": f"Data!C9:C{last_month_row}", "type": "bar"},
                    {"dataRange": f"Data!D9:D{last_month_row}", "type": "line"},
                ],
                "labelRange": f"Data!A10:A{last_month_row}",
                "aggregated": False,
                "showValues": False,
            },
        },
    ]

    dashboard = {
        "version": 21,
        "odooVersion": 12,
        "revisionId": "START_REVISION",
        "uniqueFigureIds": True,
        "settings": {
            "locale": {
                "name": "English (US)",
                "code": "en_US",
                "thousandsSeparator": ",",
                "decimalSeparator": ".",
                "dateFormat": "mm/dd/yyyy",
                "timeFormat": "hh:mm:ss",
                "formulaArgSeparator": ",",
                "weekStart": 7,
            }
        },
        "styles": {
            "1": {"textColor": "#01666b", "bold": True, "fontSize": 16},
            "2": {"textColor": "#434343", "bold": True, "fontSize": 11},
            "3": {"bold": True, "fillColor": "#f8f9fa"},
        },
        "formats": {"1": "#,##0", "2": "0.0%"},
        "borders": {
            "1": {"bottom": {"style": "thin", "color": "#CCCCCC"}},
            "2": {"top": {"style": "thin", "color": "#CCCCCC"}},
        },
        "customTableStyles": {},
        "pivots": pivots,
        "pivotNextId": len(pivots) + 1,
        "lists": {},
        "listNextId": 1,
        "globalFilters": [
            {
                "id": PERIOD_FILTER,
                "type": "date",
                "label": "Period",
                "defaultValue": "year_to_date",
                "rangeType": "relative",
            },
            {
                "id": LINE_FILTER,
                "type": "relation",
                "label": "Line",
                "modelName": "account.analytic.plan",
                "defaultValue": [],
                "defaultValueDisplayNames": [],
            },
        ],
        "chartOdooMenusReferences": {chart_id: MENU},
        "sheets": [
            sheet(
                "dashboard",
                "Dashboard",
                cells,
                styles,
                formats,
                borders,
                figures,
                conditional_formats,
                rows=last_row + 2,
                cols={
                    "0": {"size": 260},
                    **{str(i): {"size": 110} for i in range(1, MONTHS + 2)},
                },
                row_sizes={"6": {"size": 40}},
            ),
            sheet(
                "data",
                "Data",
                data,
                formats={
                    "C4": FORMATS["percent"],
                    f"B10:D{last_month_row}": FORMATS["amount"],
                },
                rows=30,
                visible=False,
            ),
        ],
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(dashboard, indent=1, ensure_ascii=False) + "\n")


def sheet(
    sheet_id,
    name,
    cells,
    styles=None,
    formats=None,
    borders=None,
    figures=None,
    conditional_formats=None,
    rows=50,
    cols=None,
    row_sizes=None,
    visible=True,
):
    return {
        "id": sheet_id,
        "name": name,
        "colNumber": 26,
        "rowNumber": rows,
        "rows": row_sizes or {},
        "cols": cols or {},
        "merges": [],
        "cells": cells,
        "styles": styles or {},
        "formats": formats or {},
        "borders": borders or {},
        "conditionalFormats": conditional_formats or [],
        "figures": figures or [],
        "tables": [],
        "areGridLinesVisible": False,
        "isVisible": visible,
        "headerGroups": {"ROW": [], "COL": []},
        "dataValidationRules": [],
        "comments": {},
    }


if __name__ == "__main__":
    build()
