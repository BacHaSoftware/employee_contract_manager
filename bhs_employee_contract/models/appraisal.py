from odoo import models, fields

class Contract(models.Model):
    _inherit = 'hr.contract'

    employee_appraisal_id = fields.Many2one('bhs.appraisal', string='Employee Appraisal', default=None)

