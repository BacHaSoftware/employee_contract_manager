# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employee Contract Manager',
    'version': '20.0.1.0.3',
    'category': 'HR',
    'sequence': 335,
    'summary': "Distinguish contract is gross or net and warn employees whose contracts are about to expire.",
    'description': """
        A product of Bac Ha Software allows to distinguish contract is gross or net
        and warn employees whose contracts are about to expire.
    """,
    'website': 'https://bachasoftware.com',
    'depends': ['hr', 'hr_holidays', 'bhs_secure_access_manager'],
    "author": "Bac Ha Software",
    'data': [
        'data/auto_notice_contract_about_expire.xml',
        'data/hr_employee_type_data.xml',
        'security/security.xml',
        'security/ir.access.csv',
        'views/hr_version_view.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_history_views.xml',
        'views/hr_leave_views_dashboard.xml',
        'views/hr_leave_views_kanban.xml',
        'views/hr_contract_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    'application': True,
    'assets': {
        'web.assets_tests': [
            'bhs_employee_contract/static/tests/tours/**/*',
        ],
    },
    'license': 'LGPL-3'
}
