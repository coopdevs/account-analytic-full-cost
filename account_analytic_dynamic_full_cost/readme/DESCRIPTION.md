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

For each company and reference date, the module:

1. Selects the computation window according to the company settings.
2. Computes a weight for each analytic plan in the hierarchy, using the analytic
   account field that corresponds to that plan dimension.
3. Computes an isolated multiplier for each productive plan from its productive
   and reproductive child branches.
4. Multiplies the isolated multiplier by its ancestor multipliers.
5. Stores the resulting multiplier on the analytic plan.

For each analytic line, the module stores the amount after applying the
full-cost multipliers of its analyzed productive dimensions:

```
full_cost_amount = amount * product(plan_full_cost_multipliers)
```

Analytic lines linked to reproductive plans are set to `0.0`, because their
weight is redistributed over productive branches.

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

## Weight Basis

The company setting **Full Cost Weight Basis** defines which analytic line
amounts are used as plan weights:

- **Expenses**: analytic lines with negative amount are used as positive expense
  magnitude.
- **Revenue**: analytic lines with positive amount are used as revenue weight.

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
