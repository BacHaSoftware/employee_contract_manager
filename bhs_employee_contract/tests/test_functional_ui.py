# -*- coding: utf-8 -*-
"""UI-level tests.

- Clickbot (run explicitly, slow: $T test --db <db> --clickbot bhs_employee_contract): Odoo's clickbot clicks every
  menu of the Employees app for each role of the module. Any JS/RPC/access error -> FAIL.
- Browser tours (standard run): the menus of the module opened directly by each role in a real browser.
"""
from datetime import date, timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

MODULE = 'bhs_employee_contract'
APPS: list[str] = ['hr.menu_hr_root']
# No base.default_user_group: on the shared test database it implies HR manager, the low roles must stay low.
ROLES = {
    'click_ecm_admin': ['base.group_user', 'base.group_system', 'hr.group_hr_manager'],
    'click_ecm_hr_manager': ['base.group_user', 'hr.group_hr_manager'],
    'click_ecm_ml': ['base.group_user', 'bhs_secure_access_manager.bhs_ml'],
    'click_ecm_trainee_mgr': ['base.group_user', f'{MODULE}.group_hr_trainee_contract_manager'],
}
TZ = 'Asia/Ho_Chi_Minh'


class ClickbotMixin:
    module = MODULE

    def _make_user(self, login, groups):
        group_ids = [self.env.ref(g).id for g in groups]
        existing = self.env['res.users'].search([('login', '=', login)])
        if existing:
            existing.write({'group_ids': [(6, 0, group_ids)], 'password': login})
            return existing
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'password': login, 'email': f'{login}@click.example.com', 'tz': TZ,
            'group_ids': [(6, 0, group_ids)],
        })

    def _employee(self, name, **vals):
        return self.env['hr.employee'].create({
            'name': name, 'date_version': date(2020, 1, 1),
            'employee_type_id': self.env.ref('hr.contract_type_employee').id, **vals,
        })

    def _seed_data(self, ml_user=None):
        """Contracts for every menu: running, subtree of the M&L user, trainee, expired (archived record)."""
        today = fields.Date.today()
        start = today - timedelta(days=200)
        trainee = self.env.ref(f'{MODULE}.employee_type_trainee')
        lead = self._employee('ECM Tour Lead Alice', contract_date_start=start,
                              user_id=ml_user.id if ml_user else False)
        self._employee('ECM Tour Sub Bob', contract_date_start=start, parent_id=lead.id,
                       contract_date_end=today + timedelta(days=20), wage=1500)
        self._employee('ECM Tour Trainee Carl', contract_date_start=start, parent_id=lead.id,
                       employee_type_id=trainee.id)
        self._employee('ECM Tour Other Dan', contract_date_start=start)
        self._employee('ECM Tour Trainee Eve', contract_date_start=start, employee_type_id=trainee.id)
        fay = self._employee('ECM Tour Expired Fay', contract_date_start=today - timedelta(days=400),
                             contract_date_end=today - timedelta(days=5))
        expired = fay.version_id
        # next contract starts later: a contract starting today is running and would list Fay by default
        self.env['hr.version'].create({'employee_id': fay.id, 'date_version': today,
                                       'contract_date_start': today + timedelta(days=10)})
        expired.action_archive()


@tagged('click_all', 'post_install', '-at_install', '-standard')
class TestFunctionalUI(ClickbotMixin, HttpCase):

    def test_clickbot_module_apps(self):
        self._seed_data()
        for login, groups in ROLES.items():
            user = self._make_user(login, groups)
            visible = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
            for xmlid in APPS:
                self.assertIn(self.env.ref(xmlid).id, visible, f"Role {login} must see app {xmlid}")
                with self.subTest(role=login, app=xmlid):
                    self.browser_js(
                        '/odoo',
                        "odoo.loader.modules.get('@web/webclient/clickbot/clickbot_loader')"
                        f".startClickEverywhere({{ xmlId: '{xmlid}', logger: true }});",
                        login=login, timeout=1200, success_signal='clickbot test succeeded')


@tagged('post_install', '-at_install')
class TestContractTours(ClickbotMixin, HttpCase):
    """Each menu of the module opened directly in a real browser by the role it is meant for."""

    def test_hr_manager_contract_list_and_expired_filter(self):
        self._seed_data()
        manager = self._make_user('tour_ecm_hr_manager', ['base.group_user', 'hr.group_hr_manager'])
        self.start_tour(f'/odoo/action-{MODULE}.action_server_hr_employee_contract_filtered',
                        'bhs_ecm_hr_manager_contracts_tour', login=manager.login)

    def test_ml_contract_list_own_subtree(self):
        ml_user = self._make_user('tour_ecm_ml', ['base.group_user', 'bhs_secure_access_manager.bhs_ml'])
        self._seed_data(ml_user=ml_user)
        # reached by clicking Employees > Contracts > Employee Contracts
        self.start_tour('/odoo', 'bhs_ecm_ml_contracts_tour', login=ml_user.login)

    def test_trainee_manager_trainee_list(self):
        self._seed_data()
        user = self._make_user('tour_ecm_trainee_mgr', ['base.group_user', f'{MODULE}.group_hr_trainee_contract_manager'])
        # reached by clicking Employees > Contracts > Trainee Contracts
        self.start_tour('/odoo', 'bhs_ecm_trainee_contracts_tour', login=user.login)
