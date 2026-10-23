# -*- coding: utf-8 -*-
"""Shared fixtures for the employee contract tests (Odoo 20).

Roles: admin, HR manager, HR officer, M&L (bhs_secure_access_manager.bhs_ml, not HR), trainee contract manager,
plain internal user and portal user.

Employees (one hr.version each, created by hr.employee.create):
- ml_emp: employee of the M&L user; sub_emp and sub_trainee report to ml_emp (subtree of the M&L user)
- other_emp: outside the M&L subtree
- trainee_emp: trainee outside the subtree
- archived_emp: non-trainee, archived employee
"""
from datetime import date, timedelta

from odoo import fields
from odoo.tests import TransactionCase, new_test_user
from odoo.tools.safe_eval import safe_eval

MODULE = 'bhs_employee_contract'
ML_GROUP = 'bhs_secure_access_manager.bhs_ml'
TRAINEE_GROUP = f'{MODULE}.group_hr_trainee_contract_manager'


class ContractCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.trainee_type = cls.env.ref(f'{MODULE}.employee_type_trainee')
        cls.regular_type = cls.env.ref('hr.contract_type_employee')

        cls.admin = cls.env.ref('base.user_admin')
        cls.hr_manager = cls._user('ecm_hr_manager', 'base.group_user,hr.group_hr_manager')
        cls.hr_officer = cls._user('ecm_hr_officer', 'base.group_user,hr.group_hr_user')
        cls.ml_user = cls._user('ecm_ml', f'base.group_user,{ML_GROUP}')
        cls.trainee_manager = cls._user('ecm_trainee_mgr', f'base.group_user,{TRAINEE_GROUP}')
        cls.plain_user = cls._user('ecm_employee', 'base.group_user')
        cls.portal_user = cls._user('ecm_portal', 'base.group_portal')

        start = cls.today - timedelta(days=200)
        cls.ml_emp = cls._employee('ECM ML Lead', user=cls.ml_user, contract_date_start=start)
        cls.sub_emp = cls._employee('ECM Sub', parent_id=cls.ml_emp.id, contract_date_start=start,
                                    contract_date_end=cls.today + timedelta(days=100), wage=1500)
        cls.sub_trainee = cls._employee('ECM Sub Trainee', parent_id=cls.ml_emp.id, contract_date_start=start,
                                        employee_type_id=cls.trainee_type.id)
        cls.other_emp = cls._employee('ECM Other', contract_date_start=start, wage=2000)
        cls.trainee_emp = cls._employee('ECM Trainee', contract_date_start=start,
                                        employee_type_id=cls.trainee_type.id)
        cls.archived_emp = cls._employee('ECM Archived', contract_date_start=start)
        cls.archived_emp.action_archive()

        cls.ml_version = cls.ml_emp.version_id
        cls.sub_version = cls.sub_emp.version_id
        cls.sub_trainee_version = cls.sub_trainee.version_id
        cls.other_version = cls.other_emp.version_id
        cls.trainee_version = cls.trainee_emp.version_id
        cls.archived_version = cls.archived_emp.with_context(active_test=False).version_id
        cls.subtree_versions = cls.ml_version | cls.sub_version | cls.sub_trainee_version
        cls.trainee_versions = cls.sub_trainee_version | cls.trainee_version
        cls.test_versions = (cls.subtree_versions | cls.other_version | cls.trainee_version
                             | cls.archived_version)

    @classmethod
    def _user(cls, login, groups):
        return new_test_user(cls.env, login=login, groups=groups, email=f'{login}@example.com',
                             name=login.replace('_', ' ').title())

    @classmethod
    def _employee(cls, name, user=None, **extra):
        vals = {
            'name': name,
            'work_email': f'{name.lower().replace(" ", ".")}@example.com',
            'date_version': date(2020, 1, 1),
            'employee_type_id': cls.regular_type.id,
        }
        if user:
            vals['user_id'] = user.id
        vals.update(extra)
        return cls.env['hr.employee'].create(vals)

    def _run_action(self, xmlid, user):
        """Return the window action dict a menu opens for ``user`` (server actions are executed)."""
        action = self.env.ref(xmlid)
        if action._name == 'ir.actions.server':
            return action.with_user(user).run()
        return self.env['ir.actions.actions'].with_user(user)._for_xml_id(xmlid)

    def _search_action(self, action, user, extra_domain=()):
        """Search hr.version like the web client does for ``action`` (domain + context), restricted to the
        test records so a real database does not change the result."""
        domain = action.get('domain') or []
        if isinstance(domain, str):
            domain = safe_eval(domain, {'uid': user.id, 'user': user})
        context = action.get('context') or {}
        if isinstance(context, str):
            context = safe_eval(context, {'uid': user.id, 'user': user})
        Version = self.env['hr.version'].with_user(user).with_context(context)
        return Version.search(list(domain) + list(extra_domain) + [('id', 'in', self.test_versions.ids)])
