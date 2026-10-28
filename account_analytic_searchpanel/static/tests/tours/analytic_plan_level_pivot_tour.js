import { registry } from "@web/core/registry";

// Row headers are indented 5px + 30px per level
const header = (title, indent) =>
    `.o_pivot th:contains('${title}')[style*='padding-left: ${5 + indent * 30}px']`;

registry.category("web_tour.tours").add("analytic_plan_level_pivot_tour", {
    steps: () => [
        {
            content: "The account of a branch without level 2 hangs from its plan",
            trigger: header("Tour Shallow Account", 2),
        },
        {
            content: "No empty plan level row is rendered",
            trigger: ".o_pivot:not(:has(th:contains('None')))",
        },
        {
            content: "The level 2 plan of a deeper branch is kept",
            trigger: header("Tour Deep Subplan", 2),
        },
        {
            content: "And its account hangs from it",
            trigger: header("Tour Deep Account", 3),
        },
        {
            content: "Plan rows are shaded by depth",
            trigger:
                "tr.o_analytic_plan_level_1 th:contains('Tour Shallow Plan'), " +
                "tr.o_analytic_plan_level_2 th:contains('Tour Deep Subplan')",
        },
        {
            content: "Account rows are not shaded",
            trigger: "tr:not([class*='o_analytic_plan_level']) th:contains('Tour Deep Account')",
        },
        {
            content: "Collapse the branch without level 2",
            trigger: header("Tour Shallow Plan", 1) + ".o_pivot_header_cell_opened",
            run: "click",
        },
        {
            content: "Expand it again by hand",
            trigger: header("Tour Shallow Plan", 1) + ".o_pivot_header_cell_closed",
            run: "click",
        },
        {
            content: "It expands down to the accounts, skipping the empty levels",
            trigger: header("Tour Shallow Account", 2),
        },
        {
            content: "Still no empty plan level row",
            trigger: ".o_pivot:not(:has(th:contains('None')))",
        },
        {
            content: "Export to a spreadsheet",
            trigger: ".o_pivot_download",
            run: "click",
        },
        {
            content: "The export did not fail",
            trigger: "body:not(:has(.o_error_dialog))",
        },
    ],
});
