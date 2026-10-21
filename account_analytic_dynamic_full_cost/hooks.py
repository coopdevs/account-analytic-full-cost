# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def post_init_hook(env):
    """Initialise the full cost of the existing analytic lines.

    Lines outside the current window keep their original amount, the ones
    inside are computed with the current multipliers of their company."""
    env.cr.execute(
        """
        UPDATE account_analytic_line
           SET full_cost_amount = amount,
               full_cost_multiplier_snapshot = 1.0
        """
    )
    env["account.analytic.line"].invalidate_model(
        ["full_cost_amount", "full_cost_multiplier_snapshot"]
    )
    env["account.analytic.plan"]._cron_recompute_full_cost()
