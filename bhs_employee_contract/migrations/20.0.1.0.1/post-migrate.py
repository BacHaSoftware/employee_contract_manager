"""Update to 20.0.1.0.1 (idempotent).

1. Contracts with the removed selection value hr.version.employee_type = 'trainee' get the module employee type
   "Trainee". Runs while the old column still exists (it is dropped at the end of the update).
2. hr.version.type_id is dropped: the number of contracts that had a value is logged.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def _retag_trainees(env):
    if not column_exists(env.cr, 'hr_version', 'employee_type'):
        _logger.warning("bhs_employee_contract: no hr_version.employee_type column, trainee re-tagging skipped: "
                        "trainee contracts must be re-tagged by hand (Employee Type = Trainee)")
        return
    trainee = env.ref('bhs_employee_contract.employee_type_trainee', raise_if_not_found=False)
    if not trainee:
        _logger.warning("bhs_employee_contract: trainee employee type missing, trainee re-tagging skipped: "
                        "trainee contracts must be re-tagged by hand (Employee Type = Trainee)")
        return
    env.cr.execute(
        """UPDATE hr_version
              SET employee_type_id = %s
            WHERE employee_type = 'trainee'
              AND employee_type_id IS DISTINCT FROM %s""",
        (trainee.id, trainee.id),
    )
    _logger.info("bhs_employee_contract: %s contract(s) re-tagged as Trainee", env.cr.rowcount)
    env['hr.version'].invalidate_model(['employee_type_id'])


def _log_dropped_type_id(env):
    if not column_exists(env.cr, 'hr_version', 'type_id'):
        return
    env.cr.execute("SELECT count(*) FROM hr_version WHERE type_id IS NOT NULL")
    _logger.info("bhs_employee_contract: hr.version.type_id dropped, %s contract(s) had a value",
                 env.cr.fetchone()[0])


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _retag_trainees(env)
    _log_dropped_type_id(env)
