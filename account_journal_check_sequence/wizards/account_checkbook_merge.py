from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Cantidad de números repetidos que se listan en el aviso del asistente.
MAX_DUPLICATES_SHOWN = 20


class AccountCheckbookMerge(models.TransientModel):
    """Unifica chequeras de diarios que emiten de la misma chequera física.

    La migración crea una chequera por diario; con este asistente se agrupan.
    Además de reasignar los diarios, mueve los cheques ya emitidos a la
    chequera destino: si no, el control de duplicados no vería los números
    que emitió cada sucursal antes de unificar.
    """

    _name = 'account.checkbook.merge'
    _description = 'Unificar chequeras'

    checkbook_ids = fields.Many2many(
        'account.checkbook',
        string='Chequeras',
        required=True,
        default=lambda self: self._default_checkbook_ids(),
    )
    target_checkbook_id = fields.Many2one(
        'account.checkbook',
        string='Chequera destino',
        required=True,
        compute='_compute_target_checkbook_id',
        store=True,
        readonly=False,
        domain="[('id', 'in', checkbook_ids)]",
    )
    next_number = fields.Char(
        string='Próximo Número de Cheque',
        required=True,
        compute='_compute_next_number',
        store=True,
        readonly=False,
        help='Por defecto, el más alto de las chequeras seleccionadas. Se respeta aunque '
             'sea menor que el actual.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía resultante',
        compute='_compute_merge_scope',
        help='Compañía que queda en la chequera destino. Vacía si los diarios son de '
             'más de una compañía: la chequera queda compartida entre compañías.',
    )
    journal_ids = fields.Many2many(
        'account.journal',
        string='Diarios',
        compute='_compute_merge_scope',
        help='Diarios que van a quedar en la chequera destino (de las compañías activas).',
    )
    duplicate_warning = fields.Text(compute='_compute_duplicate_warning')

    @api.model
    def _default_checkbook_ids(self):
        if self.env.context.get('active_model') != 'account.checkbook':
            return self.env['account.checkbook']
        return self.env['account.checkbook'].browse(self.env.context.get('active_ids', []))

    @api.model
    def _get_all_journals(self, checkbooks):
        """Diarios de las chequeras, incluidos los de compañías no activas y los archivados."""
        return self.env['account.journal'].sudo().with_context(active_test=False).search([
            ('checkbook_id', 'in', checkbooks.ids),
        ])

    @api.depends('checkbook_ids')
    def _compute_target_checkbook_id(self):
        for wizard in self:
            checkbooks = wizard.checkbook_ids._origin
            if wizard.target_checkbook_id._origin in checkbooks:
                continue
            journals = self._get_all_journals(checkbooks)
            # La que más diarios tiene: es la que menos cambios implica.
            wizard.target_checkbook_id = checkbooks.sorted(
                lambda checkbook: (-len(journals.filtered(lambda j: j.checkbook_id == checkbook)), checkbook.id)
            )[:1]

    @api.depends('checkbook_ids')
    def _compute_next_number(self):
        for wizard in self:
            checkbooks = wizard.checkbook_ids._origin
            numbers = [number for number in checkbooks.mapped('next_number') if number]
            wizard.next_number = checkbooks[:1]._get_highest_check_number(numbers) if numbers else False

    @api.depends('checkbook_ids')
    def _compute_merge_scope(self):
        for wizard in self:
            checkbooks = wizard.checkbook_ids._origin
            companies = self._get_all_journals(checkbooks).company_id
            wizard.company_id = companies.id if len(companies) == 1 else False
            wizard.journal_ids = self.env['account.journal'].search([('checkbook_id', 'in', checkbooks.ids)])

    @api.depends('checkbook_ids')
    def _compute_duplicate_warning(self):
        # sudo: la chequera puede tener cheques emitidos desde otras compañías.
        checks = self.env['l10n_latam.check'].sudo()
        for wizard in self:
            domain = [
                ('checkbook_id', 'in', wizard.checkbook_ids._origin.ids),
                ('payment_id.state', 'not in', ('draft', 'canceled')),
            ]
            groups = checks._read_group(domain, ['name'], ['__count'], having=[('__count', '>', 1)], order='name')
            if not groups:
                wizard.duplicate_warning = False
                continue
            names = [name for name, _count in groups]
            lines = []
            for name in names[:MAX_DUPLICATES_SHOWN]:
                payments = checks.search(domain + [('name', '=', name)]).payment_id
                lines.append(f"{name}: {', '.join(payments.mapped('display_name'))}")
            if len(names) > MAX_DUPLICATES_SHOWN:
                lines.append(_('… y %(count)s números más.', count=len(names) - MAX_DUPLICATES_SHOWN))
            wizard.duplicate_warning = '\n'.join([
                _('Hay números de cheque repetidos entre los ya emitidos. La unificación no los '
                  'corrige, pero conviene revisarlos:'),
                *lines,
            ])

    def action_merge(self):
        self.ensure_one()
        checkbooks = self.checkbook_ids
        target = self.target_checkbook_id
        if len(checkbooks) < 2:
            raise UserError(_('Seleccioná al menos dos chequeras para unificar.'))
        if target not in checkbooks:
            raise UserError(_('La chequera destino tiene que estar entre las seleccionadas.'))
        sources = checkbooks - target

        # Ningún pago puede publicar contra estas chequeras mientras se mueven.
        checkbooks._lock_checkbooks()
        # Primero la compañía: si no, la constraint rechaza los diarios nuevos.
        target.company_id = self.company_id
        self._get_all_journals(sources).write({'checkbook_id': target.id})
        self.env['l10n_latam.check'].sudo().search([
            ('checkbook_id', 'in', sources.ids),
        ]).write({'checkbook_id': target.id})
        # Decisión explícita del usuario: no aplica la regla de "no retroceder".
        target.next_number = self.next_number
        sources.active = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.checkbook',
            'res_id': target.id,
            'view_mode': 'form',
            'target': 'current',
        }
