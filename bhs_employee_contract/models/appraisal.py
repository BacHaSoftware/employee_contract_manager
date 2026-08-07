from odoo import models, fields

class Contract(models.Model):
    _inherit = 'hr.version'

    # Commented out: Model 'bhs.appraisal' does not exist
    # employee_appraisal_id = fields.Many2one('bhs.appraisal', string='Employee Appraisal', default=None)

