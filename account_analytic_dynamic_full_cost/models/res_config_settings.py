# Copyright 2026 Quim Rebull (Coopdevs)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    full_cost_period = fields.Selection(
        related="company_id.full_cost_period",
        readonly=False,
    )
    full_cost_weight_basis = fields.Selection(
        related="company_id.full_cost_weight_basis",
        readonly=False,
    )
    full_cost_window_days = fields.Integer(
        related="company_id.full_cost_window_days",
        readonly=False,
    )
