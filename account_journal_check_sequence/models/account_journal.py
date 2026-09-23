from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    checkbook_id = fields.Many2one(
        'account.checkbook',
        string='Chequera',
        ondelete='restrict',
        copy=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Chequera de la que salen los cheques propios de este diario. Varios diarios '
             'pueden compartir la misma chequera y consumen un único correlativo. Sin '
             'chequera, el módulo no numera los cheques de este diario.',
    )
    # La numeración está activa cuando hay chequera: el booleano ya no es una
    # fuente de verdad propia, se mantiene para no romper referencias externas.
    check_sequence_enabled = fields.Boolean(
        string='Auto-numerar Cheques Propios',
        compute='_compute_check_sequence_enabled',
        help='Campo técnico: el diario tiene asignada una chequera activa.',
    )
    # Se editan desde el diario pero viven en la chequera: si la comparten
    # varios diarios, el cambio aplica a todos.
    next_check_number = fields.Char(
        related='checkbook_id.next_number',
        readonly=False,
    )
    check_number_padding = fields.Integer(
        related='checkbook_id.padding',
        readonly=False,
    )
    checkbook_shared_journal_ids = fields.Many2many(
        'account.journal',
        string='Otros Diarios de la Chequera',
        compute='_compute_checkbook_shared_journal_ids',
    )

    @api.depends('checkbook_id.active')
    def _compute_check_sequence_enabled(self):
        for journal in self:
            journal.check_sequence_enabled = bool(journal.checkbook_id.active)

    @api.depends('checkbook_id.journal_ids')
    def _compute_checkbook_shared_journal_ids(self):
        for journal in self:
            journal.checkbook_shared_journal_ids = journal.checkbook_id.journal_ids - journal._origin

    @api.constrains('checkbook_id', 'company_id')
    def _check_checkbook_company(self):
        for journal in self:
            checkbook_company = journal.checkbook_id.company_id
            if checkbook_company and checkbook_company != journal.company_id:
                raise ValidationError(_(
                    'La chequera "%(checkbook)s" es de la compañía %(checkbook_company)s y no se '
                    'puede usar en el diario "%(journal)s" de %(journal_company)s. Para compartirla '
                    'entre compañías, dejá vacía la compañía de la chequera.',
                    checkbook=journal.checkbook_id.display_name,
                    checkbook_company=checkbook_company.display_name,
                    journal=journal.display_name,
                    journal_company=journal.company_id.display_name,
                ))
