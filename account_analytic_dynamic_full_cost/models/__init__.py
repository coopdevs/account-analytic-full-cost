# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

# Order matters: the stored computed fields of the analytic lines read the
# plan columns while the module is being installed.
from . import res_company
from . import res_config_settings
from . import analytic_plan
from . import analytic_line
from . import full_cost_report
