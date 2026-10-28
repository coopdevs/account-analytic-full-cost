This module extends analytic accounting with a dynamic full-cost calculation
based on productive and reproductive analytic plan branches.

It includes the classification of analytic plans as productive, reproductive, or
not analyzed.

## Functional Purpose

In many organisations, part of the activity is directly productive while another
part corresponds to reproductive or supporting activity such as administration,
coordination, infrastructure, shared services, or delivery management.

Reproductive activity has associated analytic weight. This module distributes
that weight across productive branches in each analytic dimension and stores the
resulting full-cost amount on analytic lines, producing a more realistic and
traceable analytic cost structure.

## How Full Cost Is Determined

The cost of the reproductive plans is spread over the productive ones,
proportionally to their **base lines**: their expenses or their revenue,
depending on the company weight basis (see below). Billing ten times more, or
spending ten times more, means bearing ten times more of the reproductive cost.

For each company and reference date, the module:

1. Selects the computation window according to the company settings.
2. Computes, for each analytic plan, the amount of its base lines and the net
   cost of all its lines (expenses minus revenue), using the analytic account
   field that corresponds to that plan dimension.
3. At each productive plan, computes a rate: the net cost of its reproductive
   child branches divided by the base lines of its productive branch. When a
   productive plan has no base lines below it, its reproductive cost goes up to
   the parent level.
4. Adds the rates of the plan and all its ancestors.
5. Stores the resulting multiplier on the analytic plan: `1 + rate` when the
   base lines are expenses (the cost grows), `1 - rate` when they are revenue
   (the margin shrinks).

For each analytic line, the module stores its full-cost amount:

- lines linked to reproductive plans: `0.0`, whatever their sign, because their
  whole balance is redistributed over productive branches;
- base lines of productive plans: `amount * product(plan_full_cost_multipliers)`;
- any other line: its original amount.

The full-cost amounts of the analysed lines therefore add up to their original
amounts: the reproductive cost is moved, never created nor lost.

Plans marked as **Not Analyzed** and every descendant below them are completely
excluded from the computation. Their analytic lines keep their original amount.
When an analytic line also has productive accounts in other dimensions, only the
not-analyzed dimensions are ignored.

## Configurable Time Window

The company parameter **Full Cost Period** controls the default look-back
window used to calculate plan weights. The default is the two-year window.
When the period is set to rolling, **Full Cost Window (Days)** defines the
number of days to look back.

Examples:

- Two-year window: full cost based on the same date two years earlier.
- Three-year window: full cost based on the same date three years earlier.
- Rolling window = 180 days: full cost based on the last six months.
- Current fiscal year: full cost based on the fiscal year of the reference date,
  from its first day. Every line of the year is valued with the same
  multipliers, so the full cost of the year adds up to its amount.

## Weight Basis

The company setting **Full Cost Weight Basis** defines the base lines, which
both weight the productive plans and carry the reproductive cost:

- **Expenses**: analytic lines with negative amount. The reproductive cost is
  added to the expenses of the productive plans.
- **Revenue**: analytic lines with positive amount. The reproductive cost is
  deducted from the revenue of the productive plans, as a percentage of their
  billing.

## Recalculation

A daily cron recomputes recent analytic lines.

A wizard allows recomputing multipliers and analytic line full-cost amounts for a
company, useful when:

- the full-cost window is changed,
- analytic entries are backdated,
- productive or reproductive weights change significantly.

Operational recalculation only updates analytic lines inside the current
full-cost window. Lines outside that window keep their latest calculated
`full_cost_amount`. This is intentional: once an entry falls outside the active
calculation window, its operational value is treated as a stable historical
result instead of being continuously rewritten by later cost structures. For
historical analysis at another date, use the historical full-cost report; it
calculates the applicable window and ratios on the fly without changing stored
analytic lines.

## Typical Use Cases

1. Project costing
2. Cooperative / social economy organisations
3. Internal rate validation
4. Management accounting / controlling
5. Forecasting and budgeting
