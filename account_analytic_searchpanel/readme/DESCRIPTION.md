This module improves analytic line navigation by adding an Analytic Plan search
panel to the analytic line search view.

Analytic plans can be configured as explorable or not explorable in that search
panel. The panel keeps the analytic plan hierarchy, using the plan `parent_id`,
so users can navigate the plan structure instead of a flat list. This lets each
database decide which analytic dimensions are meaningful for navigation,
without imposing that the panel always follows the project dimension.

It also adds Analytic Plan and Analytic Account group-by entries, and opens the
standard analytic item actions grouped by Analytic Plan and then Analytic
Account.

Analytic lines also get one group-by per hierarchy level of their analytic
plan, counted top-down from the root plan (Root, Level 1 ... Level 4). Unlike
the standard `Project (n)` group-bys, which count upwards from the plan of the
analytic account, a given level always means the same depth in the hierarchy,
so grouping by Root, then Level 1, then Level 2 unfolds the plan tree
consistently even when accounts sit at different depths. Only the analytic
account column (`account_id`) is split into levels, up to five levels.

In the Analytic Items list view, plan levels a branch does not reach are skipped:
when grouping by a plan level only yields the empty group and a deeper grouping
follows, the list groups by the next one instead of showing a chain of empty
groups. This only applies to the analytic items views (through their own
`js_class`); other views keep the standard behaviour.

The same skipping applies to the Analytic Items pivot view, which also unfolds
down through the empty levels when a branch is expanded by hand, and shades the
plan rows by depth so that the hierarchy reads at a glance.
