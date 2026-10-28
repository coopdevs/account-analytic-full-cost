This module gives an overview of the analytic accounting of the company, month
by month, with the revenue and the expenses of every analytic plan.

Analytic lines get two stored measures, **Revenue** (the amount when it is
positive) and **Expenses** (the amount when it is negative, kept negative), so
that revenue and expenses can be shown side by side and add up to the amount.

It adds:

- **Accounting > Reporting > Monthly Analytics**: a pivot with the whole
  project plan hierarchy down to the analytic accounts in rows, the months in
  columns, and the revenue, expenses and amount as measures, with the totals of
  every level of the hierarchy. It relies on the plan levels of
  `account_analytic_searchpanel`, so the levels a branch does not reach are
  skipped and the plan rows are shaded by depth.
- An **Analytics** spreadsheet dashboard, in the Finance section of the
  Dashboards app: key figures (revenue, expenses, result and margin), revenue
  and expenses by month, the result by line (first level of the project plan),
  the monthly result by line, and the analytic accounts with the highest
  expenses and revenue. It can be filtered by period and by line.
