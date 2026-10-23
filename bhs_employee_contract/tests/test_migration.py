# -*- coding: utf-8 -*-
"""migrations/20.0.1.0.1/post-migrate.py re-tags the trainee contracts (hr_version.employee_type = 'trainee')
with the module employee type "Trainee"."""
import importlib.util

from odoo.tests import tagged
from odoo.tools.misc import file_path
from odoo.tools.sql import column_exists

from .common import MODULE, ContractCommon

SCRIPT = f'{MODULE}/migrations/20.0.1.0.1/post-migrate.py'


def _load_script():
    spec = importlib.util.spec_from_file_location('bhs_ecm_post_migrate', file_path(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestMigration(ContractCommon):

    def setUp(self):
        super().setUp()
        self.script = _load_script()
        self.legacy = self._employee('ECM Legacy Trainee', contract_date_start=self.today)
        self.version = self.legacy.version_id
        self.intern = self.env.ref('hr.contract_type_intern')
        self.version.employee_type_id = self.intern  # e.g. a generic 19 -> 20 mapping chose "Intern"
        self.env.flush_all()

    def _add_legacy_column(self):
        # DDL is transactional in PostgreSQL: rolled back with the test
        if not column_exists(self.env.cr, 'hr_version', 'employee_type'):
            self.env.cr.execute("ALTER TABLE hr_version ADD COLUMN employee_type varchar")

    def test_retag_19_trainee_contract(self):
        self._add_legacy_column()
        self.env.cr.execute("UPDATE hr_version SET employee_type = 'trainee' WHERE id = %s", [self.version.id])
        self.env.cr.execute("UPDATE hr_version SET employee_type = 'employee' WHERE id = %s", [self.other_version.id])
        with self.assertLogs(level='INFO') as logs:
            self.script.migrate(self.env.cr, '19.0.1.0')
        self.assertTrue(any('re-tagged as Trainee' in line for line in logs.output))
        self.env.invalidate_all()
        self.assertEqual(self.version.employee_type_id, self.trainee_type)
        self.assertTrue(self.version.bhs_is_trainee)
        self.assertEqual(self.other_version.employee_type_id, self.regular_type)
        visible = self.env['hr.version'].with_user(self.trainee_manager).search([('id', '=', self.version.id)])
        self.assertEqual(visible, self.version)

    def test_retag_is_idempotent(self):
        self._add_legacy_column()
        self.env.cr.execute("UPDATE hr_version SET employee_type = 'trainee' WHERE id = %s", [self.version.id])
        self.script.migrate(self.env.cr, '19.0.1.0')
        self.env.cr.execute("SELECT write_date FROM hr_version WHERE id = %s", [self.version.id])
        before = self.env.cr.fetchone()
        self.script.migrate(self.env.cr, '19.0.1.0')
        self.env.cr.execute("SELECT employee_type_id, write_date FROM hr_version WHERE id = %s", [self.version.id])
        employee_type_id, write_date = self.env.cr.fetchone()
        self.assertEqual(employee_type_id, self.trainee_type.id)
        self.assertEqual((write_date,), before)

    def test_without_legacy_column_nothing_changes(self):
        if column_exists(self.env.cr, 'hr_version', 'employee_type'):
            self.env.cr.execute("ALTER TABLE hr_version DROP COLUMN employee_type")
        with self.assertLogs(level='WARNING') as logs:
            self.script.migrate(self.env.cr, '19.0.1.0')
        self.assertTrue(any('re-tagged by hand' in line for line in logs.output))
        self.env.invalidate_all()
        self.assertEqual(self.version.employee_type_id, self.intern)
        self.assertFalse(self.version.bhs_is_trainee)
