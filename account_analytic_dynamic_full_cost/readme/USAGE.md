## 1. Configure Analytic Plans

Each analytic plan can be marked as:

- **Productive**: activity that receives full-cost allocation.
- **Reproductive**: supporting activity whose weight must be spread.
- **Not Analyzed**: activity excluded from full-cost analysis together with all descendants.

To configure:

1. Go to *Accounting -> Configuration -> Analytic Accounting -> Analytic Plans*.
2. Open a plan.
3. Set **Full Cost Role** to *Productive*, *Reproductive*, or *Not Analyzed*.

Analytic lines derive their full-cost role from the analyzed analytic accounts
set on the line. In Odoo's multidimensional analytic model, each root analytic
plan has its own account field; dimensions marked as *Not Analyzed* are ignored.

## 2. Configure Company Full-Cost Settings

Go to *Settings -> Companies -> [Your Company]* and set:

- **Full Cost Period**
- **Full Cost Weight Basis**
- **Full Cost Window (Days)**

The window determines which analytic lines are considered when recomputing plan
weights. The weight basis determines whether those weights come from expenses
or revenue.

## 3. Recompute Multipliers and Amounts

Use *Accounting -> Analytic Accounting -> Recompute analytic full cost*.

Select:

- Company
- Whether analytic lines should also be recomputed

The wizard recomputes the current plan multipliers using today's date and the
company window configuration. If line recomputation is enabled, it then updates
`full_cost_amount` only on analytic lines inside the current full-cost window.

Analytic lines outside the current window keep their latest calculated
`full_cost_amount`. This avoids continuously rewriting old operational analytic
figures when today's cost structure changes. To analyse another date or an old
period, use the historical full-cost report, which calculates the relevant
window and ratios on the fly without updating stored analytic lines.

## 4. Reporting

Use *Accounting -> Reporting -> Historical Full-Cost Analysis* to select an
analysis date. The report calculates the window and multipliers on the fly for
that date; it does not store historical ratios.

You can also analyse current full cost in analytic reporting views by using:

- `full_cost_amount`
- `full_cost_role`

This allows reporting at analytic account and full-cost role level.
