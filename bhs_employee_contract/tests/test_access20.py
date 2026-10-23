# -*- coding: utf-8 -*-
"""Access rights per role on hr.version after the Odoo 20 move to ir.access.

Pairs ("cannot do X" / "can still do own part") for every role: M&L reads only its own subtree, the trainee
manager writes only trainee contracts and no salary structure type.
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import ContractCommon


@tagged('post_install', '-at_install')
class TestAccess20(ContractCommon):

    def _visible(self, user):
        return self.env['hr.version'].with_user(user).search([('id', 'in', self.test_versions.ids)])

    # ---- admin / HR manager / HR officer -------------------------------------------------------------------
    def test_admin_and_hr_roles_see_every_contract(self):
        for user in (self.admin, self.hr_manager, self.hr_officer):
            with self.subTest(user=user.login):
                self.assertEqual(self._visible(user), self.test_versions)

    def test_hr_officer_reads_wage_and_dates(self):
        """Module rule: wage and contract dates readable by HR officers (core 20: wage manager)."""
        version = self.sub_version.with_user(self.hr_officer)
        self.assertEqual(version.wage, 1500)
        self.assertEqual(version.contract_date_end, self.sub_version.contract_date_end)

    def test_hr_officer_cannot_read_employee_type(self):
        """Core 20 keeps employee_type_id for HR managers only (not widened by the module)."""
        with self.assertRaises(AccessError):
            self.sub_version.with_user(self.hr_officer).employee_type_id  # noqa: B018

    def test_hr_manager_writes_contract(self):
        self.other_version.with_user(self.hr_manager).write({'wage': 2100, 'salary_type': 'gross'})
        self.assertEqual(self.other_version.wage, 2100)
        self.assertEqual(self.other_version.salary_type, 'gross')

    # ---- M&L (only the own subtree) -----------------------------------------------------------------------
    def test_ml_sees_only_own_subtree(self):
        self.assertEqual(self._visible(self.ml_user), self.subtree_versions)

    def test_ml_cannot_read_contract_outside_subtree(self):
        with self.assertRaises(AccessError):
            self.other_version.with_user(self.ml_user).read(['wage'])

    def test_ml_reads_wage_and_dates_of_subtree(self):
        data = self.sub_version.with_user(self.ml_user).read(['wage', 'contract_date_start', 'contract_date_end',
                                                               'days_left', 'salary_type', 'bhs_is_trainee'])[0]
        self.assertEqual(data['wage'], 1500)
        self.assertEqual(data['contract_date_end'], self.sub_version.contract_date_end)
        self.assertEqual(data['salary_type'], 'net')
        self.assertFalse(data['bhs_is_trainee'])

    def test_ml_cannot_write_or_create(self):
        with self.assertRaises(AccessError):
            self.sub_version.with_user(self.ml_user).write({'wage': 1})
        with self.assertRaises(AccessError):
            self.env['hr.version'].with_user(self.ml_user).create({'name': 'ECM ML new'})

    def test_ml_without_employee_sees_nothing(self):
        lonely = self._user('ecm_ml_lonely', 'base.group_user,bhs_secure_access_manager.bhs_ml')
        self.assertFalse(self._visible(lonely))

    def test_ml_cannot_read_employee_type(self):
        with self.assertRaises(AccessError):
            self.sub_version.with_user(self.ml_user).employee_type_id  # noqa: B018

    # ---- Trainee manager (only trainee contracts) -----------------------------------------------------------
    def test_trainee_manager_sees_only_trainee_contracts(self):
        self.assertEqual(self._visible(self.trainee_manager), self.trainee_versions)

    def test_trainee_manager_writes_trainee_contract(self):
        self.trainee_version.with_user(self.trainee_manager).write({'name': 'ECM trainee renamed'})
        self.assertEqual(self.trainee_version.name, 'ECM trainee renamed')

    def test_trainee_manager_reads_updates_deletes_but_cannot_create(self):
        """HR managers create contracts (employee_type_id is HR-manager-only); trainee managers
        keep read/update/delete on trainee contracts and get no create right (no "New" button)."""
        Version = self.env['hr.version'].with_user(self.trainee_manager)
        with self.assertRaises(AccessError):
            Version.check_access('create')
        self.assertFalse(Version.has_access('create'))
        self.trainee_version.with_user(self.trainee_manager).check_access('read')
        self.trainee_version.with_user(self.trainee_manager).check_access('write')
        self.trainee_version.with_user(self.trainee_manager).check_access('unlink')
        with self.assertRaises(AccessError):
            self.other_version.with_user(self.trainee_manager).check_access('unlink')

    def test_trainee_manager_unlinks_trainee_contract(self):
        """Core 20 checks the employee keeps a version by reading version_ids (HR officers only): the delete right
        of the trainee manager must still work on a trainee contract that is not the last one."""
        extra = self.env['hr.version'].create({
            'employee_id': self.trainee_emp.id, 'date_version': '2019-06-06',
            'employee_type_id': self.trainee_type.id,
        })
        extra.with_user(self.trainee_manager).unlink()
        self.assertFalse(extra.exists())
        self.assertTrue(self.trainee_version.exists())

    def test_trainee_manager_cannot_unlink_last_trainee_contract(self):
        with self.assertRaises(ValidationError):
            self.trainee_version.with_user(self.trainee_manager).unlink()

    def test_trainee_manager_cannot_write_employee_contract(self):
        with self.assertRaises(AccessError):
            self.other_version.with_user(self.trainee_manager).write({'name': 'hacked'})
        with self.assertRaises(AccessError):
            self.other_version.with_user(self.trainee_manager).unlink()

    def test_trainee_manager_has_no_salary_structure_type_access(self):
        with self.assertRaises(AccessError):
            self.env['hr.payroll.structure.type'].with_user(self.trainee_manager).search([])
        with self.assertRaises(AccessError):
            self.env['hr.payroll.structure.type'].with_user(self.trainee_manager).create({'name': 'ECM hack'})

    def test_hr_manager_keeps_salary_structure_type_access(self):
        structure = self.env['hr.payroll.structure.type'].with_user(self.hr_manager).create({'name': 'ECM struct'})
        self.assertTrue(structure.exists())

    def test_hr_manager_implies_trainee_manager(self):
        self.assertTrue(self.hr_manager.has_group('bhs_employee_contract.group_hr_trainee_contract_manager'))

    # ---- plain employee / portal ---------------------------------------------------------------------------
    def test_employee_and_portal_cannot_read_contracts(self):
        for user in (self.plain_user, self.portal_user):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.env['hr.version'].with_user(user).search([])
                with self.assertRaises(AccessError):
                    self.sub_version.with_user(user).read(['wage', 'contract_date_start', 'contract_date_end'])

    def test_employee_cannot_read_contract_dates_on_employee(self):
        with self.assertRaises(AccessError):
            self.sub_emp.with_user(self.plain_user).read(['contract_date_end'])

    def test_bhs_is_trainee_search_does_not_leak_to_employee(self):
        with self.assertRaises(AccessError):
            self.env['hr.version'].with_user(self.plain_user).search([('bhs_is_trainee', '=', True)])
