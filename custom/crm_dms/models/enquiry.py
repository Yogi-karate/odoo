from odoo import api, fields, models, tools, SUPERUSER_ID,_

from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
import re


class Enquiry(models.Model):
    _name = "dms.enquiry"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utm.mixin']

    name = fields.Char('Enquiry', index=True)
    partner_id = fields.Many2one('res.partner', string='Customer', track_visibility='onchange', track_sequence=1,
                                index=True,
                                 help="Linked partner (optional). Usually created when converting the lead. You can find a partner by its Name, TIN, Email or Internal Reference.")
    active = fields.Boolean('Active', default=True, track_visibility=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', oldname='section_id',
                              default=lambda self: self.env['crm.team'].sudo()._get_default_team_id(
                                  user_id=self.env.uid),
                              index=True, track_visibility='onchange',
                              help='When sending mails, the default email address is taken from the Sales Team.')
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                              default=lambda self: self.env.user)
    # kanban_state = fields.Selection(
    #    [('grey', 'No next activity planned'), ('red', 'Next activity late'), ('green', 'Next activity is planned')],
    #   string='Kanban State', compute='_compute_kanban_state')

    state = fields.Selection([
        ('open', 'Open'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', track_sequence=3,
        default='open')
    product_id = fields.Many2one('product.template', string='Product', required=True)
    model_name = fields.Char('Model', compute='_compute_model_name')
    product_color = fields.Many2one('product.template.attribute.value', string='Color')
    product_variant = fields.Many2one('product.template.attribute.value', string='Variant')
    opportunity_ids = fields.One2many('crm.lead', 'enquiry_id', string='Opportunities')
    type_ids = fields.Many2many('dms.opportunity.type', 'enquiry_opportunity_type_rel', 'enquiry_id',
                                'opportunity_type_id', string='Types', required=True,
                                track_visibility='onchange')
    categ_ids = fields.Many2many('product.category', 'enquiry_category_rel', 'enquiry_id',
                                'id', string='Opportunity Categories', compute='_compute_categories',
                                track_visibility='onchange')
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can provide product details', readonly=True)
    finance_updatable = fields.Boolean(compute='_compute_finance_updatable', string='Can provide finance details',
                                       readonly=True)
    insurance_updatable = fields.Boolean(compute='_compute_insurance_updatable', string='Can provide insurance details',
                                       readonly=True)
    opportunity_count = fields.Integer('# Meetings', compute='_compute_opportunity_count')
    date_follow_up = fields.Date('Follow-Up Date', help="Estimate of the date on which the opportunity will be won.", required=True)
    partner_name = fields.Char('Customer Name', required=True)
    partner_mobile = fields.Char('Customer Mobile', required=True)
    partner_email = fields.Char('Customer Email')
    description = fields.Text('Notes', track_visibility='onchange', track_sequence=6)

    #finance fields added by Yoganand on 31-01-2019
    financier_name = fields.Many2one('res.bank', string='Financier', help="Bank for finance")
    finance_amount = fields.Float('Amount', digits=dp.get_precision('Product Price'), default=0.0)
    finance_agreement_date = date_order = fields.Datetime(string='Finance Agreement Date', default=fields.Datetime.now)
    loan_tenure = fields.Char('Tenure', help="Loan Tenure")
    loan_amount = fields.Float('Loan Amount', digits=dp.get_precision('Product Price'), default=0.0)
    loan_approved_amount = fields.Float('Approved Amount', digits=dp.get_precision('Product Price'), default=0.0)
    loan_rate = fields.Float("Rate of Interest", digits=(2, 2), help='The rate of interest for loan')
    loan_emi = fields.Float('EMI', digits=dp.get_precision('Product Price'), default=0.0)
    loan_commission = fields.Float('Commission ', digits=dp.get_precision('Product Price'), default=0.0)
    finance_type = fields.Selection([
        ('in', 'in-house'),
        ('out', 'out-house'),
    ], string='Finance Type', store=True, default='out')

    # insurance fields added by Yoganand on 31/01/2019
    insurance_company = fields.Char('Insurance Company',String = "Insurance Company")
    policy_no = fields.Char('Policy No.')
    insurance_valid_from = fields.Datetime(string='Insurance Valid From')
    insurance_valid_to = fields.Datetime(string='Insurance Valid To')
    insurance_type = fields.Selection([
        ('in', 'in-house'),
        ('out', 'out-house'),
    ], string='Insurance Type', store=True, default='out')
    policy_punch_via = fields.Selection([
        ('covernote', 'Covernote'),
        ('hap', 'HAP'),
        ('nonhap','Non-HAP')
    ], string='Policy Punch Via', store=True, default='covernote')
    currency_id = fields.Many2one(
        'res.currency', string='Currency')
    idv = fields.Monetary('IDV',currency_field='currency_id')
    premium_amount = fields.Monetary('Premium Amount',currency_field='currency_id')

    @api.depends('type_ids')
    @api.multi
    def _compute_product_updatable(self):
        is_vehicle = False
        for type_id in self.type_ids:
            if 'vehicle' in type_id.name.lower() or 'new' in type_id.name.lower():
                is_vehicle = True
                print("returning TRUE")
        self.product_updatable = is_vehicle

    @api.depends('type_ids')
    @api.multi
    def _compute_finance_updatable(self):
        is_finance = False
        for type_id in self.type_ids:
            if 'finance' in type_id.name.lower():
                is_finance = True
                print("returning TRUE")
        self.finance_updatable = is_finance

    @api.depends('type_ids')
    @api.multi
    def _compute_insurance_updatable(self):
        is_insurance = False
        for type_id in self.type_ids:
            if 'insurance' in type_id.name.lower():
                is_insurance = True
                print("returning TRUE")
        self.insurance_updatable = is_insurance

    @api.constrains('partner_mobile')
    @api.multi
    def _valid_mobile(self):
        pattern = re.compile(r'^[0-9]{10}')
        for enquiry in self:
            if not pattern.match(enquiry.partner_mobile):
                raise ValidationError(_("Please Enter a Valid Mobile Number"))

    @api.multi
    def _compute_categories(self):
        ids = []
        for type_id in self.type_ids:
            ids.append(type_id.categ_id.id)
        self.categ_ids = ids


    @api.onchange('type_ids')
    def _on_change_type(self):
        print(self.type_ids)
        self._compute_categories()
        return

    #@api.onchange('product_id')
    #def _compute_model_name(self):
        #return self.product_id.name

    @api.multi
    def _compute_opportunity_count(self):
        # meeting_data = self.env['calendar.event'].read_group([('enquiry_id', 'in', self.ids)], ['enquiry_id'],
        # ['enquiry_id'])
        # mapped_data = {m['enquiry_id'][0]: m['enquiry_id_count'] for m in meeting_data}
        for enquiry in self:
            enquiry.opportunity_count = len(enquiry.opportunity_ids)

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        print(vals)
        if 'name' not in vals:
            print("hello")
            product_name = self.env['product.template'].browse(vals['product_id']).name
            vals['name'] = product_name
            print(product_name)
            if 'partner_name' in vals:
                vals['name'] += '/' + vals['partner_name']
        res = super(Enquiry, self).create(vals)
        res._create_opportunities()
        return res

    @api.model
    def _prepare_opportunities(self, type):
        print(self)
        customer = self._create_lead_partner()
        return {
            'name': type.name + '/' + self.product_id.name,
            'partner_id': customer.id,
            'enquiry_id': self.id,
            'opportunity_type': type.id,
            'user_id': type.team_id.user_id.id,
            'team_id': type.team_id.id,
            'date_deadline' : self.date_follow_up,
            'type': 'opportunity'
        }

    @api.model
    def _schedule_follow_up(self, lead):
        lead.activity_schedule(
            'crm_dms.mail_activity_data_follow_up',
            user_id=lead.user_id.id,
            note=_("Follow up  on  <a href='#' data-oe-model='%s' data-oe-id='%d'>%s</a> for customer <a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                  lead._name, lead.id, lead.name,
                  lead.partner_id._name, lead.partner_id.id, lead.partner_id.display_name),
            date_deadline=self.date_follow_up)


    @api.multi
    def _create_opportunities(self):
        #print(vals)
        lead = self.env['crm.lead']
        for enquiry in self:
            print(enquiry)
            if not enquiry.opportunity_ids:
                leads = []
                for type in enquiry.type_ids:
                    res = self._prepare_opportunities(type)
                    id = lead.create(res)
                    print(id)
                    self._schedule_follow_up(id)
            else:
                print("Not creating Opportunities as they already exist")

    @api.multi
    def write(self, vals):
        print("write enquiry !!!!!! ---------------------|||||||||||||||||||||||||||||||")
        print(self)
        return super(Enquiry, self).write(vals)

    def action_create_opportunities(self):
        print("Creating Opportunities")
        self._create_opportunities(None)

    @api.multi
    def _create_lead_partner_data(self, name, is_company, parent_id=False):
        """ extract data from lead to create a partner
            :param name : furtur name of the partner
            :param is_company : True if the partner is a company
            :param parent_id : id of the parent partner (False if no parent)
            :returns res.partner record
        """
        email_split = tools.email_split(self.partner_email)
        return {
            'name': name,
            'user_id': self.env.context.get('default_user_id') or self.user_id.id,
            'comment': self.description,
            'team_id': self.team_id.id,
            'mobile': self.partner_mobile,
            'email': email_split[0] if email_split else False,
            'type': 'contact'
        }

    @api.multi
    def _create_lead_partner(self):
        """ Create a partner from lead data
            :returns res.partner record
        """
        Partner = self.env['res.partner']
        #contact_name = self.contact_name
        #if not contact_name:
        #    contact_name = Partner._parse_partner_name(self.email_from)[0] if self.email_from else False

        #if self.partner_name:
        #    partner_company = Partner.create(self._create_lead_partner_data(self.partner_name, True))
        #elif self.partner_id:
        #    partner_company = self.partner_id
        #else:
        #    partner_company = None

        #if contact_name:
        #    return Partner.create(
        #        self._create_lead_partner_data(contact_name, False, partner_company.id if partner_company else False))

        #if partner_company:
        #    return partner_company
        if self.partner_name:
            return Partner.create(self._create_lead_partner_data(self.partner_name, False))



