# -*- coding: utf-8 -*-

from odoo import models, fields


class BhsVersionEmployee(models.Model):
    _inherit = 'hr.employee'

    version_name = fields.Char(
        readonly=False,
        related="version_id.name",
        groups="hr.group_hr_manager,bhs_secure_access_manager.bhs_ml"
    )
    contract_date_start = fields.Date(
        related='version_id.contract_date_start',
        string='Contract Start Date',
        groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml"
    )
    contract_date_end = fields.Date(
        related='version_id.contract_date_end',
        string='Contract End Date',
        groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml"
    )


class HrVersion(models.Model):
    _inherit = 'hr.version'

    # Redeclared to grant read access to the bhs_ml group (record access is limited by ir.access)
    contract_date_start = fields.Date(groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml")
    contract_date_end = fields.Date(groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml")
    wage = fields.Monetary(groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml", tracking=False)
    name = fields.Char(tracking=False)
    # Odoo 20 orders hr.version by date_version (HR officers only) and checks field access when ordering:
    # without this the M&L and trainee manager roles cannot list the contracts they are allowed to read.
    date_version = fields.Date(
        groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml,"
               "bhs_employee_contract.group_hr_trainee_contract_manager")
