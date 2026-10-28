import { registry } from "@web/core/registry";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { ListRenderer } from "@web/views/list/list_renderer";
import { analyticListView } from "@analytic/views/list/list_view";

export const PLAN_LEVEL_FIELD_PREFIX = "analytic_plan_level_";

export class AnalyticPlanLevelModel extends RelationalModel {
    /**
     * Skip the plan levels a branch does not reach: when grouping by a plan
     * level only yields the empty group and a deeper grouping follows, group
     * by the next one instead of showing a chain of "None" groups.
     */
    async _loadGroupedList(config) {
        const response = await super._loadGroupedList(config);
        const [groupByName, ...nextGroupBy] = config.groupBy;
        if (
            groupByName.startsWith(PLAN_LEVEL_FIELD_PREFIX) &&
            nextGroupBy.length &&
            response.groups.length === 1 &&
            !response.groups[0].value
        ) {
            config.groupBy = nextGroupBy;
            config.groups = {};
            delete config.currentGroups;
            return this._loadGroupedList(config);
        }
        return response;
    }
}

export class AnalyticPlanLevelListRenderer extends ListRenderer {
    /**
     * The standard level is computed from the number of remaining group-bys,
     * which is wrong once plan levels are skipped: use the depth of the group
     * in the group tree instead.
     */
    getGroupLevel(group) {
        const findLevel = (list, level) => {
            for (const sibling of list.groups || []) {
                if (sibling.id === group.id) {
                    return level;
                }
                if (!sibling.isFolded) {
                    const subLevel = findLevel(sibling.list, level + 1);
                    if (subLevel !== undefined) {
                        return subLevel;
                    }
                }
            }
        };
        return findLevel(this.props.list, 0) ?? super.getGroupLevel(group);
    }
}

export const analyticPlanLevelListView = {
    ...analyticListView,
    Model: AnalyticPlanLevelModel,
    Renderer: AnalyticPlanLevelListRenderer,
};

registry.category("views").add("analytic_plan_level_list", analyticPlanLevelListView);
