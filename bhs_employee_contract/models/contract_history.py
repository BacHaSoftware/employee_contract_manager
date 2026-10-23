from datetime import datetime

from odoo import api, fields, models, _
from odoo.fields import Domain

TRAINEE_TYPE_XMLID = 'bhs_employee_contract.employee_type_trainee'


class Contract(models.Model):
    _inherit = 'hr.version'

    # compute_sudo: the list views of the module show days_left to roles that cannot read contract_date_end
    # (trainee contract manager); record access still applies to the contract itself.
    days_left = fields.Integer('Days left', compute="_compute_days_left", compute_sudo=True)
    salary_type = fields.Selection([
        ('net', 'NET'),
        ('gross', 'GROSS')],
        string='Salary type', default='net')
    employee_name = fields.Char(related='employee_id.name')
    # employee_type_id is restricted to HR managers in Odoo 20: this narrow flag lets the other roles of the module
    # (M&L, trainee contract manager) filter trainee contracts without reading the employee type itself.
    bhs_is_trainee = fields.Boolean(
        'Trainee Contract', compute='_compute_bhs_is_trainee', search='_search_bhs_is_trainee', compute_sudo=True)
    # Core active_employee is restricted to HR officers; the module menus filter on it for the other roles too.
    bhs_employee_active = fields.Boolean('Employee Active', related='employee_id.active')
    # End date the "about to expire" notice was last sent for, written on every version of the contract: the cron
    # notifies each contract end date only once, a new end date (renewal / extension) makes it eligible again.
    bhs_expiry_notice_end_date = fields.Date('Expiry Notice Sent For', copy=False, readonly=True)

    # Do not update the employee department from the contract
    def _get_employee_vals_to_update(self):
        self.ensure_one()
        vals = {'contract_id': self.id}
        if self.job_id and self.job_id != self.employee_id.job_id:
            vals['job_id'] = self.job_id.id
        return vals

    @api.ondelete(at_uninstall=False)
    def _unlink_except_last_version(self):
        # Core 20 reads employee_id.version_ids (HR officers only) for this check: run it as superuser so the
        # trainee contract manager can use the delete right ir.access gives. Only record sets are compared.
        return super(Contract, self.sudo())._unlink_except_last_version()

    @api.depends('contract_date_end')
    def _compute_days_left(self):
        for rec in self:
            rec.days_left = 0
            if rec.contract_date_end:
                diff = (rec.contract_date_end - fields.Date.today()).days
                rec.days_left = diff

    def _bhs_trainee_type(self):
        return self.env.ref(TRAINEE_TYPE_XMLID, raise_if_not_found=False)

    @api.depends('employee_type_id')
    def _compute_bhs_is_trainee(self):
        trainee = self._bhs_trainee_type()
        for version in self:
            version.bhs_is_trainee = bool(trainee) and version.employee_type_id == trainee

    def _search_bhs_is_trainee(self, operator, value):
        if operator not in ('in', 'not in'):
            return NotImplemented
        trainee = self._bhs_trainee_type()
        if trainee:
            # privileged sub-query: only the trainee flag leaks, never the employee type itself
            trainee_query = self.sudo().with_context(active_test=False)._search(
                [('employee_type_id', '=', trainee.id)])
            is_trainee = Domain('id', 'in', trainee_query)
        else:
            is_trainee = Domain.FALSE
        wanted = {bool(v) for v in value}
        if operator == 'not in':
            wanted = {True, False} - wanted
        if wanted == {True, False}:
            return Domain.TRUE
        if wanted == {True}:
            return is_trainee
        if wanted == {False}:
            return ~is_trainee
        return Domain.FALSE

    def _auto_notice_contract_about_expire(self, time=None):
        versions = self.env['hr.version'].search([('active', '=', True), ('contract_date_end', '!=', False)])
        # Core syncs the contract dates on every version of a contract: the versions of one employee sharing the
        # same start and end dates are one contract, notified once.
        contracts = versions.grouped(lambda v: (v.employee_id, v.contract_date_start, v.contract_date_end))
        time_date = time and datetime.strptime(time, '%Y-%m-%d %H:%M:%S').date()
        for (employee, _date_start, date_end), contract in contracts.items():
            if date_end in contract.mapped('bhs_expiry_notice_end_date'):
                # already notified for this end date
                continue
            if not contract._bhs_expiry_notice_due(time_date):
                continue
            con = employee.version_id if employee.version_id in contract else max(
                contract, key=lambda v: v.date_version)
            con._bhs_send_expiry_notice()
            contract.bhs_expiry_notice_end_date = date_end

    def _bhs_expiry_notice_due(self, time_date=None):
        """Whether the contract (versions sharing the same dates) is in its notice window."""
        con = self[:1]
        if time_date and con.contract_date_end == time_date:
            return True
        diff = (con.contract_date_end - fields.Date.today()).days
        # contracts that already ended are not "about to expire"
        return 0 <= diff <= con.employee_id.company_id.contract_expiration_notice_period

    def _bhs_send_expiry_notice(self):
        self.ensure_one()
        con = self
        email_from = con.employee_id.company_id.email
        values = {
            'subject': _("Employee %s's contract is about to expire", con.employee_id.name),
            'body': _("Employee %s's contract will expire on %s", con.employee_id.name, con.contract_date_end),
            'email_from': email_from,
            'reply_to': email_from,
            'model': 'hr.version',
            'res_id': con.id,
            'reply_to_force_new': True,
            'email_add_signature': True,
            'partner_ids': [con.hr_responsible_id.partner_id.id if con.hr_responsible_id else False, con.employee_id.parent_id.user_id.partner_id.id if con.employee_id.parent_id and con.employee_id.parent_id.user_id else False]
        }
        values['partner_ids'] = [pid for pid in values['partner_ids'] if pid]
        message = self.env['mail.message'].create(values)
        # Odoo 20: _notify_thread(message, **kwargs), recipients are read from the message
        con._notify_thread(message)
