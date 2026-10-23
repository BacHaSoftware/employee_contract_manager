# -*- coding: utf-8 -*-
"""Business behaviour of the module on Odoo 20: menus/actions per role, computed fields, search filters, views and
the expiry notification cron."""
from datetime import timedelta
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.addons.mail.tests.common import MockEmail
from odoo.tests import Form, freeze_time, tagged
from odoo.tools.safe_eval import safe_eval

from .common import MODULE, ContractCommon

EMPLOYEE_ACTION = f'{MODULE}.action_server_hr_employee_contract_filtered'
TRAINEE_ACTION = f'{MODULE}.hr_trainee_contract_history_view_list_action'


@tagged('post_install', '-at_install')
class TestFunctional(ContractCommon, MockEmail):

    def _filter_domain(self, user, action, name):
        """Domain of filter ``name`` in the search view the action opens for ``user``."""
        views = self.env['hr.version'].with_user(user).get_views(
            [(action.get('search_view_id') and action['search_view_id'][0], 'search')])
        arch = etree.fromstring(views['views']['search']['arch'])
        node = arch.find(f".//filter[@name='{name}']")
        self.assertIsNotNone(node, f"filter {name} missing")
        return safe_eval(node.get('domain'))

    # ---- Employee Contracts menu ---------------------------------------------------------------------------
    def test_hr_manager_employee_contracts_running_non_trainee(self):
        ended = self._employee('ECM Ended', contract_date_start=self.today - timedelta(days=400),
                               contract_date_end=self.today - timedelta(days=10))
        self.test_versions |= ended.version_id
        action = self._run_action(EMPLOYEE_ACTION, self.hr_manager)
        self.assertEqual(action['res_model'], 'hr.version')
        self.assertEqual(safe_eval(action['context'])['search_default_running_contract'], 1)
        running = self._filter_domain(self.hr_manager, action, 'running_contract')
        found = self._search_action(action, self.hr_manager, running)
        self.assertEqual(found, self.ml_version | self.sub_version | self.other_version)

    def test_running_filter_includes_contract_starting_today(self):
        starting = self._employee('ECM Starts Today', contract_date_start=self.today,
                                  contract_date_end=self.today + timedelta(days=90))
        self.test_versions |= starting.version_id
        action = self._run_action(EMPLOYEE_ACTION, self.hr_manager)
        running = self._filter_domain(self.hr_manager, action, 'running_contract')
        self.assertIn(starting.version_id, self._search_action(action, self.hr_manager, running))

    def test_hr_manager_employee_contracts_without_filter(self):
        action = self._run_action(EMPLOYEE_ACTION, self.hr_manager)
        found = self._search_action(action, self.hr_manager)
        self.assertNotIn(self.trainee_version, found)
        self.assertNotIn(self.sub_trainee_version, found)
        self.assertNotIn(self.archived_version, found)
        self.assertIn(self.other_version, found)

    def test_ml_employee_contracts_own_subtree_non_trainee(self):
        action = self._run_action(EMPLOYEE_ACTION, self.ml_user)
        running = self._filter_domain(self.ml_user, action, 'running_contract')
        self.assertEqual(self._search_action(action, self.ml_user, running), self.ml_version | self.sub_version)
        found = self._search_action(action, self.ml_user)
        self.assertEqual(found, self.ml_version | self.sub_version)
        self.assertEqual((found & self.sub_version).wage, 1500)

    def test_trainee_contracts_menu_only_trainees(self):
        for user in (self.trainee_manager, self.hr_manager):
            with self.subTest(user=user.login):
                action = self._run_action(TRAINEE_ACTION, user)
                self.assertEqual(self._search_action(action, user), self.trainee_versions)

    def test_trainee_menu_excludes_archived_employee(self):
        self.trainee_emp.action_archive()
        action = self._run_action(TRAINEE_ACTION, self.trainee_manager)
        self.assertEqual(self._search_action(action, self.trainee_manager), self.sub_trainee_version)

    def test_menus_visibility(self):
        menus = self.env['ir.ui.menu']
        contract_menu = self.env.ref(f'{MODULE}.hr_menu_contract')
        trainee_menu = self.env.ref(f'{MODULE}.hr_menu_trainee_contract')
        visible = menus.with_user(self.hr_manager)._visible_menu_ids()
        self.assertIn(contract_menu.id, visible)
        self.assertIn(trainee_menu.id, visible)
        for user in (self.plain_user, self.hr_officer):
            with self.subTest(user=user.login):
                self.assertNotIn(contract_menu.id, menus.with_user(user)._visible_menu_ids())
                self.assertNotIn(trainee_menu.id, menus.with_user(user)._visible_menu_ids())

    def test_menus_reachable_for_ml_and_trainee_manager(self):
        """The menus are not under 'Management' (HR officers only), which would hide them from these roles."""
        menus = self.env['ir.ui.menu']
        contract_menu = self.env.ref(f'{MODULE}.hr_menu_contract')
        trainee_menu = self.env.ref(f'{MODULE}.hr_menu_trainee_contract')
        ml_visible = menus.with_user(self.ml_user)._visible_menu_ids()
        self.assertIn(contract_menu.id, ml_visible)
        self.assertIn(contract_menu.parent_id.id, ml_visible)
        self.assertNotIn(trainee_menu.id, ml_visible)
        trainee_visible = menus.with_user(self.trainee_manager)._visible_menu_ids()
        self.assertIn(trainee_menu.id, trainee_visible)
        self.assertIn(trainee_menu.parent_id.id, trainee_visible)
        self.assertNotIn(contract_menu.id, trainee_visible)
        plain_visible = menus.with_user(self.plain_user)._visible_menu_ids()
        self.assertNotIn(contract_menu.parent_id.id, plain_visible)
        self.assertNotIn(trainee_menu.parent_id.id, plain_visible)

    # ---- fields --------------------------------------------------------------------------------------------
    def test_days_left_and_salary_type_default(self):
        self.assertEqual(self.sub_version.days_left, 100)
        self.assertEqual(self.other_version.days_left, 0)
        self.assertEqual(self.sub_version.salary_type, 'net')

    def test_bhs_is_trainee(self):
        self.assertTrue(self.trainee_version.bhs_is_trainee)
        self.assertFalse(self.other_version.bhs_is_trainee)
        Version = self.env['hr.version']
        domain = [('id', 'in', self.test_versions.ids)]
        self.assertEqual(Version.search(domain + [('bhs_is_trainee', '=', True)]), self.trainee_versions)
        self.assertEqual(Version.search(domain + [('bhs_is_trainee', '!=', True)]),
                         self.test_versions - self.trainee_versions)
        self.assertEqual(Version.search(domain + [('bhs_is_trainee', '=', False)]),
                         self.test_versions - self.trainee_versions)

    def test_employee_version_name_and_dates(self):
        self.sub_emp.write({'version_name': 'ECM contract A'})
        self.assertEqual(self.sub_version.name, 'ECM contract A')
        self.assertEqual(self.sub_emp.contract_date_end, self.sub_version.contract_date_end)
        data = self.sub_emp.with_user(self.hr_officer).read(['contract_date_start', 'contract_date_end'])[0]
        self.assertEqual(data['contract_date_end'], self.sub_version.contract_date_end)

    def test_type_id_dropped(self):
        """The module field hr.version.type_id (hr.contract.type) is dropped."""
        self.assertNotIn('type_id', self.env['hr.version']._fields)

    # ---- search filters ------------------------------------------------------------------------------------
    def test_expired_filter_includes_archived(self):
        ended = self._employee('ECM Expired', contract_date_start=self.today - timedelta(days=400),
                               contract_date_end=self.today - timedelta(days=1))
        version = ended.version_id
        # a new contract follows the expired one, then the expired record is archived
        current = self.env['hr.version'].create({'employee_id': ended.id, 'date_version': self.today,
                                                 'contract_date_start': self.today})
        version.action_archive()
        self.assertFalse(version.active)
        self.test_versions |= version | current
        action = self._run_action(EMPLOYEE_ACTION, self.hr_manager)
        # the search view the Employee Contracts action opens (module view), not the default one
        self.assertEqual(action['search_view_id'][0],
                         self.env.ref(f'{MODULE}.hr_version_search_view_inherit_running_expired').id)
        views = self.env['hr.version'].with_user(self.hr_manager).get_views([(action['search_view_id'][0], 'search')])
        node = etree.fromstring(views['views']['search']['arch']).find(".//filter[@name='expired_contracts']")
        filter_context = safe_eval(node.get('context'))
        self.assertEqual(filter_context, {'active_test': False})
        domain = safe_eval(node.get('domain'))
        # the filter alone (its own context), like the web client after toggling it
        found = self.env['hr.version'].with_user(self.hr_manager).with_context(**filter_context).search(
            domain + [('id', 'in', self.test_versions.ids)])
        self.assertEqual(found, version)
        self.assertNotIn(current, found)

    def test_search_view_employee_type_for_managers_only(self):
        def search_arch(user):
            views = self.env['hr.version'].with_user(user).get_views([(False, 'search')])
            return etree.fromstring(views['views']['search']['arch'])
        manager_arch = search_arch(self.hr_manager)
        node = manager_arch.find(".//filter[@name='contract_type']")
        self.assertIsNotNone(node)
        self.assertEqual(safe_eval(node.get('context')), {'group_by': 'employee_type_id'})
        self.assertIsNotNone(manager_arch.find(".//field[@name='employee_type_id']"))
        for user in (self.hr_officer, self.ml_user, self.trainee_manager):
            with self.subTest(user=user.login):
                arch = search_arch(user)
                self.assertIsNone(arch.find(".//filter[@name='contract_type']"))
                self.assertIsNone(arch.find(".//field[@name='employee_type_id']"))

    def test_search_filters_usable_by_each_role(self):
        """Every filter / group-by the search view shows to a role runs without AccessError (menus reachable)."""
        for user in (self.hr_manager, self.hr_officer, self.ml_user, self.trainee_manager):
            Version = self.env['hr.version'].with_user(user)
            arch = etree.fromstring(Version.get_views([(False, 'search')])['views']['search']['arch'])
            for node in arch.iter('filter'):
                if node.get('invisible') == '1':
                    continue
                with self.subTest(user=user.login, filter=node.get('name')):
                    if node.get('domain'):
                        domain = safe_eval(node.get('domain'), {'context_today': lambda: self.today})
                        Version.search(domain + [('id', 'in', self.test_versions.ids)])
                    group_by = safe_eval(node.get('context') or '{}').get('group_by')
                    if group_by:
                        Version.formatted_read_group([('id', 'in', self.test_versions.ids)], [group_by], ['__count'])
        trainee_arch = self.env['hr.version'].with_user(self.trainee_manager).get_views([(False, 'search')])
        self.assertNotIn('running_contract', trainee_arch['views']['search']['arch'])

    # ---- views ---------------------------------------------------------------------------------------------
    def test_views_load_for_each_role(self):
        Version = self.env['hr.version']
        for user in (self.hr_manager, self.hr_officer, self.ml_user, self.trainee_manager):
            for view_type in ('list', 'form', 'kanban', 'search'):
                with self.subTest(user=user.login, view_type=view_type):
                    Version.with_user(user).get_views([(False, view_type)])
        Version.with_user(self.hr_manager).get_views([(self.env.ref(f'{MODULE}.hr_contract_form_view').id, 'form')])
        self.env['hr.employee'].with_user(self.hr_manager).get_views([(False, 'form')])
        self.env['hr.leave'].with_user(self.hr_manager).get_views([(False, 'kanban'), (False, 'calendar')])

    def test_contract_form(self):
        form = Form(self.sub_version.with_user(self.hr_manager), view=f'{MODULE}.hr_contract_form_view')
        self.assertEqual(form.employee_name, 'ECM Sub')
        form.wage = 1800
        form.save()
        self.assertEqual(self.sub_version.wage, 1800)

    def test_employee_form_version_name(self):
        form = Form(self.sub_emp.with_user(self.hr_manager))
        form.version_name = 'ECM via form'
        form.save()
        self.assertEqual(self.sub_version.name, 'ECM via form')

    # ---- expiry notification cron --------------------------------------------------------------------------
    def _run_cron(self, today):
        cron = self.env.ref(f'{MODULE}.hr_ir_cron_notice_contract_about_expire')
        with patch.object(fields.Date, 'today', lambda *a, **k: today), self.mock_mail_gateway():
            cron.ir_actions_server_id.with_user(cron.user_id).run()

    def _notices(self, version):
        return self.env['mail.message'].search([('model', '=', 'hr.version'), ('res_id', '=', version.id),
                                                ('subject', 'ilike', 'about to expire')])

    def test_cron_notifies_contract_about_to_expire(self):
        responsible = self._user('ecm_responsible', 'base.group_user,hr.group_hr_user')
        boss_user = self._user('ecm_boss', 'base.group_user')
        boss = self._employee('ECM Boss', user=boss_user)
        end = self.today + timedelta(days=60)
        emp = self._employee('ECM Expiring', parent_id=boss.id, contract_date_start=self.today - timedelta(days=30),
                             contract_date_end=end)
        version = emp.version_id
        version.hr_responsible_id = responsible
        self.env.company.contract_expiration_notice_period = 7
        fixed_today = end - timedelta(days=5)
        self._run_cron(fixed_today)
        notice = self._notices(version)
        self.assertEqual(len(notice), 1)
        self.assertEqual(notice.partner_ids, responsible.partner_id | boss_user.partner_id)
        self.assertIn('ECM Expiring', notice.body)
        notified = notice.notification_ids.res_partner_id
        self.assertEqual(notified, responsible.partner_id | boss_user.partner_id)

    def test_cron_skips_contract_far_from_end(self):
        self.env.company.contract_expiration_notice_period = 7
        self._run_cron(self.sub_version.contract_date_end - timedelta(days=30))
        self.assertFalse(self._notices(self.sub_version))
        self.assertFalse(self._notices(self.other_version))  # no end date

    def test_cron_skips_expired_contract(self):
        self.env.company.contract_expiration_notice_period = 7
        end = self.sub_version.contract_date_end
        self._run_cron(end + timedelta(days=3))
        self.assertFalse(self._notices(self.sub_version))

    def test_cron_notifies_contract_ending_today(self):
        self.env.company.contract_expiration_notice_period = 7
        self._run_cron(self.sub_version.contract_date_end)
        self.assertEqual(len(self._notices(self.sub_version)), 1)

    def test_cron_specific_time_argument(self):
        """The cron method also accepts a date (``time``) notifying contracts ending exactly that day."""
        self.env.company.contract_expiration_notice_period = 0
        end = self.sub_version.contract_date_end
        with patch.object(fields.Date, 'today', lambda *a, **k: end - timedelta(days=50)), self.mock_mail_gateway():
            self.env['hr.version']._auto_notice_contract_about_expire(time=f'{end} 00:00:00')
        self.assertEqual(len(self._notices(self.sub_version)), 1)

    # ---- expiry notice sent once per end date --------------------------------------------------------------
    def _run_cron_frozen(self, day):
        """Run the cron as its user with the clock frozen on ``day``."""
        cron = self.env.ref(f'{MODULE}.hr_ir_cron_notice_contract_about_expire')
        with freeze_time(day), self.mock_mail_gateway():
            cron.ir_actions_server_id.with_user(cron.user_id).run()

    def test_cron_notifies_once_over_several_days_in_window(self):
        self.env.company.contract_expiration_notice_period = 7
        end = self.sub_version.contract_date_end
        for days_before in (5, 4, 3):
            self._run_cron_frozen(end - timedelta(days=days_before))
        self.assertEqual(len(self._notices(self.sub_version)), 1)
        self.assertEqual(self.sub_version.bhs_expiry_notice_end_date, end)

    def test_cron_notifies_again_after_end_date_change(self):
        self.env.company.contract_expiration_notice_period = 7
        end = self.sub_version.contract_date_end
        self._run_cron_frozen(end - timedelta(days=5))
        self.assertEqual(len(self._notices(self.sub_version)), 1)
        # next day, still inside the window of the same end date: the marker blocks a second notice
        self._run_cron_frozen(end - timedelta(days=4))
        self.assertEqual(len(self._notices(self.sub_version)), 1)
        self.assertEqual(self.sub_version.bhs_expiry_notice_end_date, end)
        # extension: the new end date is notified once when it enters the window
        new_end = end + timedelta(days=30)
        self.sub_version.contract_date_end = new_end
        self._run_cron_frozen(new_end - timedelta(days=5))
        self._run_cron_frozen(new_end - timedelta(days=4))
        self.assertEqual(len(self._notices(self.sub_version)), 2)
        self.assertEqual(self.sub_version.bhs_expiry_notice_end_date, new_end)

    def test_cron_outside_window_leaves_marker_empty(self):
        self.env.company.contract_expiration_notice_period = 7
        self._run_cron_frozen(self.sub_version.contract_date_end - timedelta(days=30))
        self.assertFalse(self._notices(self.sub_version))
        self.assertFalse(self.sub_version.bhs_expiry_notice_end_date)

    def test_cron_ended_contract_leaves_marker_empty(self):
        self.env.company.contract_expiration_notice_period = 7
        self._run_cron_frozen(self.sub_version.contract_date_end + timedelta(days=3))
        self.assertFalse(self._notices(self.sub_version))
        self.assertFalse(self.sub_version.bhs_expiry_notice_end_date)

    def test_cron_time_argument_skips_already_notified_contract(self):
        self.env.company.contract_expiration_notice_period = 7
        end = self.sub_version.contract_date_end
        self._run_cron_frozen(end - timedelta(days=5))
        with freeze_time(end - timedelta(days=4)), self.mock_mail_gateway():
            self.env['hr.version']._auto_notice_contract_about_expire(time=f'{end} 00:00:00')
        self.assertEqual(len(self._notices(self.sub_version)), 1)
        self.assertEqual(self.sub_version.bhs_expiry_notice_end_date, end)

    # ---- one notice per contract period, whatever the number of versions ----------------------------------
    def _add_version(self, days_ago=10, wage=1600):
        """Add a version to sub_emp inside its current contract (same start / end dates)."""
        version = self.sub_emp.create_version({'date_version': self.today - timedelta(days=days_ago), 'wage': wage})
        self.assertEqual(version.contract_date_start, self.sub_version.contract_date_start)
        self.assertEqual(version.contract_date_end, self.sub_version.contract_date_end)
        return version

    def test_cron_notifies_once_per_contract_with_several_versions(self):
        self.env.company.contract_expiration_notice_period = 7
        new_version = self._add_version()
        self.assertEqual(self.sub_emp.version_id, new_version)
        end = self.sub_version.contract_date_end
        self._run_cron_frozen(end - timedelta(days=5))
        self._run_cron_frozen(end - timedelta(days=4))
        self.assertFalse(self._notices(self.sub_version))
        self.assertEqual(len(self._notices(new_version)), 1)
        self.assertEqual(self.sub_version.bhs_expiry_notice_end_date, end)
        self.assertEqual(new_version.bhs_expiry_notice_end_date, end)

    def test_cron_version_added_in_window_is_not_notified_again(self):
        self.env.company.contract_expiration_notice_period = 7
        end = self.sub_version.contract_date_end
        self._run_cron_frozen(end - timedelta(days=5))
        self.assertEqual(len(self._notices(self.sub_version)), 1)
        new_version = self._add_version(days_ago=5)
        self._run_cron_frozen(end - timedelta(days=4))
        self.assertEqual(len(self._notices(self.sub_version)), 1)
        self.assertFalse(self._notices(new_version))

    def test_cron_notifies_latest_version_of_contract_that_is_not_current(self):
        """The current version belongs to a newer contract: the notice of the old contract goes on the latest
        version (by date_version) of the old contract."""
        self.env.company.contract_expiration_notice_period = 7
        old_end = self.today - timedelta(days=10)
        self.sub_version.contract_date_end = old_end
        old_latest = self._add_version(days_ago=50)
        new_contract = self.sub_emp.create_version({
            'date_version': self.today - timedelta(days=5),
            'contract_date_start': self.today - timedelta(days=5),
            'contract_date_end': self.today + timedelta(days=300),
        })
        self.assertEqual(self.sub_emp.version_id, new_contract)
        self.assertEqual(old_latest.contract_date_end, old_end)
        self._run_cron_frozen(old_end - timedelta(days=3))
        self.assertEqual(len(self._notices(old_latest)), 1)
        self.assertFalse(self._notices(self.sub_version))
        self.assertFalse(self._notices(new_contract))
        self.assertEqual(self.sub_version.bhs_expiry_notice_end_date, old_end)
        self.assertEqual(old_latest.bhs_expiry_notice_end_date, old_end)
        self.assertFalse(new_contract.bhs_expiry_notice_end_date)
