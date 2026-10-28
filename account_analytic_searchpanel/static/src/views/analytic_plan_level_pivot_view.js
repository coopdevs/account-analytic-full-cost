import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { PivotModel } from "@web/views/pivot/pivot_model";
import { analyticPivotView } from "@analytic/views/pivot/pivot_view";
import { AnalyticPivotRenderer } from "@analytic/views/pivot/pivot_renderer";
import { PLAN_LEVEL_FIELD_PREFIX } from "./analytic_plan_level_list_view";

export class AnalyticPlanLevelPivotModel extends PivotModel {
    /**
     * Expanding a row by hand goes on through the plan levels its branch
     * does not reach, as the initial load already does.
     */
    async expandGroup(groupId, type) {
        await super.expandGroup(groupId, type);
        if (type !== "row") {
            return;
        }
        const tree = this._findGroup(this.data.rowGroupTree, groupId[0]);
        const [subTree] = tree.directSubTrees.values();
        if (
            tree.directSubTrees.size === 1 &&
            this._isEmptyPlanLevel(subTree.root.values) &&
            subTree.root.values.length < this.metaData.fullRowGroupBys.length
        ) {
            await this.expandGroup([subTree.root.values, []], type);
        }
    }

    /**
     * Skip the rows of the plan levels a branch does not reach: an empty
     * plan level group that is the only child of its parent is not shown and
     * its children are moved one level up. The plan level rows also get
     * their depth, to shade them.
     */
    _getTableRows(tree, columns) {
        const rows = super._getTableRows(tree, columns);
        if (tree !== this.data.rowGroupTree) {
            // Inner call of the recursion, the root call does the job
            return rows;
        }
        const nodes = [];
        const stack = [];
        for (const row of rows) {
            const node = { row, children: [] };
            while (stack.length && stack.at(-1).row.indent >= row.indent) {
                stack.pop();
            }
            (stack.length ? stack.at(-1).children : nodes).push(node);
            stack.push(node);
        }
        const result = [];
        const emit = (node, siblings, shift) => {
            if (
                siblings.length === 1 &&
                node.children.length &&
                this._isEmptyPlanLevel(node.row.groupId[0])
            ) {
                for (const child of node.children) {
                    emit(child, node.children, shift + 1);
                }
                return;
            }
            const row = { ...node.row, indent: node.row.indent - shift };
            if (this._isPlanLevelRow(row.groupId[0])) {
                row.analyticPlanLevel = row.indent;
            }
            result.push(row);
            for (const child of node.children) {
                emit(child, node.children, shift);
            }
        };
        for (const node of nodes) {
            emit(node, nodes, 0);
        }
        return result;
    }

    /**
     * The exported rows also carry the depth of the plan level rows, to shade
     * them in the spreadsheet as on the screen.
     */
    exportData() {
        const data = super.exportData();
        const rows = this.getTable().rows;
        data.rows.forEach((row, index) => {
            row.analytic_level = rows[index].analyticPlanLevel || 0;
        });
        return data;
    }

    _isPlanLevelRow(rowValues) {
        if (!rowValues.length) {
            return false;
        }
        const groupBy = this.metaData.fullRowGroupBys[rowValues.length - 1];
        return groupBy.split(":")[0].startsWith(PLAN_LEVEL_FIELD_PREFIX);
    }

    _isEmptyPlanLevel(rowValues) {
        return this._isPlanLevelRow(rowValues) && rowValues.at(-1) === false;
    }
}

export class AnalyticPlanLevelPivotRenderer extends AnalyticPivotRenderer {
    // Adds a class with the depth of the plan level rows
    static template = "account_analytic_searchpanel.PivotRenderer";

    /**
     * Export with the context of the table (filters, search panel, groupings,
     * measures) and the plan level of every row, to a route that writes it
     * with the colors of the screen.
     */
    onDownloadButtonClicked() {
        if (this.model.getTableWidth() > 16384) {
            return super.onDownloadButtonClicked();
        }
        const table = this.model.exportData();
        table.export_info = this.getExportInfo();
        download({
            url: "/account_analytic_searchpanel/pivot/export_xlsx",
            data: { data: new Blob([JSON.stringify(table)], { type: "application/json" }) },
        });
    }

    getExportInfo() {
        const searchModel = this.env.searchModel;
        const fieldOf = (groupId) =>
            searchModel.getSearchItems((item) => item.groupId === groupId)[0]?.fieldName;
        return {
            // Whole domain of the table, to tell the budgets and the period
            // it covers
            domain: this.model.searchParams.domain,
            facets: searchModel.facets
                .filter((facet) => facet.type === "field")
                .map((facet) => ({ field: fieldOf(facet.groupId), values: facet.values })),
            panel: searchModel
                .getSections((section) => section.type === "category")
                .filter((section) => section.activeValueId)
                .map((section) => ({
                    field: section.fieldName,
                    id: section.activeValueId,
                    name: section.values.get(section.activeValueId)?.display_name || "",
                })),
        };
    }
}

export const analyticPlanLevelPivotView = {
    ...analyticPivotView,
    Model: AnalyticPlanLevelPivotModel,
    Renderer: AnalyticPlanLevelPivotRenderer,
};

registry.category("views").add("analytic_plan_level_pivot", analyticPlanLevelPivotView);
