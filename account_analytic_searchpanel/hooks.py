def post_init_hook(env):
    env.cr.execute(
        """
        UPDATE account_analytic_plan
        SET show_in_analytic_searchpanel = TRUE
        WHERE show_in_analytic_searchpanel IS NULL
        """
    )
