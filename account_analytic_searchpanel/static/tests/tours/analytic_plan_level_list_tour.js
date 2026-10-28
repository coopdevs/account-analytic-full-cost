import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("analytic_plan_level_list_tour", {
    steps: () => [
        {
            content: "Open the level 1 group of a branch without level 2",
            trigger: ".o_group_header:contains('Tour Shallow Plan')",
            run: "click",
        },
        {
            content: "The account group shows right below, no empty level 2 group",
            trigger: ".o_group_header:contains('Tour Shallow Account')",
        },
        {
            content: "No empty plan level group was rendered",
            trigger: ".o_list_table:not(:has(.o_group_header:contains('None')))",
        },
        {
            content: "Open the level 1 group of a branch with level 2",
            trigger: ".o_group_header:contains('Tour Deep Plan')",
            run: "click",
        },
        {
            content: "The level 2 group is kept when the branch reaches it",
            trigger: ".o_group_header:contains('Tour Deep Subplan')",
        },
        {
            content: "A branch with skipped levels keeps the indentation of its siblings",
            trigger:
                ".o_group_header:contains('Tour Shallow Plan') .o_group_caret[style*='--o-list-group-level: 0']",
        },
        {
            content: "Its children are indented one level below it",
            trigger:
                ".o_group_header:contains('Tour Shallow Account') .o_group_caret[style*='--o-list-group-level: 1']",
        },
    ],
});
