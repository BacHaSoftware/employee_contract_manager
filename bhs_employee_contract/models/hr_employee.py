# -*- coding: utf-8 -*-
# Merged from bhs_version module

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

    # Khai báo lại các trường để cấp quyền truy cập cho nhóm bhs_ml
    contract_date_start = fields.Date(groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml")
    contract_date_end = fields.Date(groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml")
    wage = fields.Monetary(groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml", tracking=False)
    type_id = fields.Many2one('hr.contract.type', groups="hr.group_hr_user,bhs_secure_access_manager.bhs_ml")
    name = fields.Char(tracking=False)
