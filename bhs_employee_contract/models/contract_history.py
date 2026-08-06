from odoo import api, fields, models, tools, _
from collections import defaultdict
from datetime import datetime

class Contract(models.Model):
    _inherit = 'hr.version'

    days_left = fields.Integer('Days left', compute="_compute_days_left")
    salary_type = fields.Selection([
        ('net', 'NET'),
        ('gross', 'GROSS')],
        string='Salary type', default='net')
    employee_name = fields.Char(related='employee_id.name')
    
    # ko cập nhật data department
    def _get_employee_vals_to_update(self):
        self.ensure_one()
        vals = {'contract_id': self.id}
        if self.job_id and self.job_id != self.employee_id.job_id:
            vals['job_id'] = self.job_id.id
        return vals

    @api.depends('contract_date_end')
    def _compute_days_left(self):
        for rec in self:
            rec.days_left = 0
            if rec.contract_date_end:
                diff = (rec.contract_date_end - fields.Date.today()).days
                rec.days_left = diff

    def _auto_notice_contract_about_expire(self,time=None):
        contracts = self.env['hr.version'].search([('active', '=', True),('contract_date_end','!=', False)])
        for con in contracts:
            if time and con.contract_date_end == datetime.strptime(time, '%Y-%m-%d %H:%M:%S').date():
                send_notification = True
            else:
                diff = (con.contract_date_end - fields.Date.today()).days
                send_notification = diff <= con.employee_id.company_id.contract_expiration_notice_period
            if send_notification:
                email_from = con.employee_id.company_id.email
                values = {
                    'subject': _("Employee %s's contract is about to expire", con.employee_id.name),
                    'body': _("Employee %s's contract will expire on %s", con.employee_id.name, con.contract_date_end),
                    'record_name': _("Employee %s's contract", con.employee_id.name),
                    'email_from': email_from,
                    'reply_to': email_from,
                    'model': 'hr.version',
                    'res_id': con.id,
                    'reply_to_force_new': True,
                    'email_add_signature': True,
                    'partner_ids': [con.hr_responsible_id.partner_id.id if con.hr_responsible_id else False, con.employee_id.parent_id.user_id.partner_id.id if con.employee_id.parent_id and con.employee_id.parent_id.user_id else False]
                }
                # Filter out False values
                values['partner_ids'] = [pid for pid in values['partner_ids'] if pid]
                message = self.env['mail.message'].create(values)
                self._notify_thread(message, values)