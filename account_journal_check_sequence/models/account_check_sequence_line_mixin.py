from odoo import api, fields, models


class AccountCheckSequenceLineMixin(models.AbstractModel):
    """Línea de cheque numerada por la chequera del diario.

    Comparten esta lógica ``l10n_latam.check`` (líneas del pago) y
    ``l10n_latam.payment.register.check`` (líneas del wizard de registro). Solo
    difieren en el campo que apunta al registro que tiene la chequera, que cada
    modelo declara en ``_check_sequence_parent_field``.
    """

    _name = 'account.check.sequence.line.mixin'
    _description = 'Línea de cheque numerada por la chequera del diario'

    # Campo Many2one hacia el registro que tiene el diario (pago o wizard).
    _check_sequence_parent_field = 'payment_id'

    autofilled_check_number = fields.Char(
        string='Número Autocompletado',
        copy=False,
        help='Campo técnico: último número que asignó automáticamente la chequera del '
             'diario. Si el usuario edita el número, deja de coincidir con él y el '
             'módulo pasa a respetar el valor cargado a mano.',
    )

    @api.model
    def _resolve_check_sequence_parent(self, vals=None):
        """Resuelve el pago o wizard del que sale la chequera, de forma segura.

        ``active_id`` solo se considera cuando el modelo activo coincide con el
        del padre: en el wizard de registro, por ejemplo, apunta a un
        ``account.move``, y browsearlo a ciegas traería el número de otra
        chequera o directamente un MissingError.
        """
        field_name = self._check_sequence_parent_field
        comodel = self._fields[field_name].comodel_name
        context = self.env.context
        parent_id = (vals or {}).get(field_name) or context.get('default_%s' % field_name)
        if not parent_id and context.get('active_model') == comodel:
            parent_id = context.get('active_id')
        # En un onchange sobre un registro nuevo el id puede ser un NewId: no
        # hay padre persistido del que tomar la chequera.
        if not isinstance(parent_id, int):
            return self.env[comodel]
        return self.env[comodel].browse(parent_id).exists()

    @api.model
    def _get_next_check_number_for_line(self, parent, extra_used=None):
        """Próximo número libre considerando las líneas ya cargadas en el padre."""
        journal = parent._check_sequence_journal()
        if not journal:
            return False
        used_numbers = parent._get_check_numbers_used() + list(extra_used or [])
        start_from = journal._get_highest_check_number(used_numbers) if used_numbers else False
        return journal._peek_check_numbers(1, start_from=start_from)[0]

    @api.model
    def default_get(self, fields_list):
        """Sugiere el número de la línea nueva sin repetir el de las anteriores.

        El camino principal es el contexto de la One2many: el padre publica ahí
        el próximo número libre (``check_sequence_next_number``), que ya tiene
        en cuenta las líneas cargadas en el cliente y todavía no guardadas.
        El contador del diario no sirve por sí solo porque no avanza hasta
        postear el pago, así que todas las líneas nuevas nacerían iguales.
        """
        res = super().default_get(fields_list)
        if 'name' in fields_list and not res.get('name'):
            number = self.env.context.get('check_sequence_next_number')
            if not number:
                parent = self._resolve_check_sequence_parent(res)
                number = parent and self._get_next_check_number_for_line(parent)
            if number:
                res['name'] = number
                res['autofilled_check_number'] = number
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Numera las líneas sin nombre encadenando el correlativo del diario.

        Cubre lo que no pasa por el formulario: importaciones, duplicar un
        pago, o guardar una One2many con varias líneas nuevas de una sola vez.
        """
        assigned_by_parent = {}
        for vals in vals_list:
            parent = self._resolve_check_sequence_parent(vals)
            if not parent:
                continue
            already_assigned = assigned_by_parent.setdefault(parent.id, [])
            if vals.get('name'):
                # Se registra igual: durante el create del padre las líneas
                # hermanas del mismo lote todavía no se ven en la One2many, así
                # que este es el único rastro de que ese número ya está tomado.
                already_assigned.append(vals['name'])
                continue
            number = self._get_next_check_number_for_line(parent, already_assigned)
            if not number:
                continue
            vals['name'] = number
            vals['autofilled_check_number'] = number
            already_assigned.append(number)
        return super().create(vals_list)
