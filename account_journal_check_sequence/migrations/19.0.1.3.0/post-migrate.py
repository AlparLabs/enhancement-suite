import logging

from odoo import SUPERUSER_ID, api
from odoo.addons.account_journal_check_sequence.models.account_checkbook import (
    DEFAULT_CHECK_NUMBER_PADDING,
    MAX_CHECK_NUMBER_PADDING,
)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración 19.0.1.2.0 → 19.0.1.3.0

    El contador de cheques pasa del diario a la chequera (``account.checkbook``):

    1. Por cada diario de banco con la numeración activa y sin chequera, se
       crea una chequera con su próximo número, su padding y su compañía, y se
       le asigna. No se fusiona nada: no hay forma de saber qué diarios
       comparten chequera física. Eso se hace después con el asistente
       "Unificar chequeras".
    2. Se completa la chequera emisora en los cheques propios ya emitidos,
       para que el control de números duplicados cubra la historia.

    Las columnas viejas de ``account_journal`` quedan como respaldo. El
    script es idempotente: solo toca diarios y cheques sin chequera.
    """
    if not version:
        return
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'account_journal'
           AND column_name = 'check_sequence_enabled'
    """)
    if not cr.fetchone():
        return

    # ORM para crear las chequeras: account.journal.name es jsonb traducible.
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT id, next_check_number, check_number_padding
          FROM account_journal
         WHERE check_sequence_enabled IS TRUE
           AND type = 'bank'
           AND checkbook_id IS NULL
         ORDER BY id
    """)
    rows = cr.fetchall()
    # El contexto vacío lee el nombre traducible del diario en en_US, que en las
    # bases argentinas queda activo ("Bank" en los diarios del plan contable, o
    # el nombre en inglés anterior a un renombre). El nombre de la chequera no
    # es traducible: se toma en el idioma de la compañía (o del admin).
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    fallback_lang = admin.lang if admin else None
    for journal_id, next_number, padding in rows:
        journal = env['account.journal'].browse(journal_id)
        lang = journal.company_id.partner_id.lang or fallback_lang
        name = journal.with_context(lang=lang).name if lang else journal.name
        valid_padding = padding and 1 <= padding <= MAX_CHECK_NUMBER_PADDING
        journal.checkbook_id = env['account.checkbook'].create({
            'name': name,
            'next_number': (next_number or '').strip() or '00000001',
            'padding': padding if valid_padding else DEFAULT_CHECK_NUMBER_PADDING,
            'company_id': journal.company_id.id,
        })
    if rows:
        _logger.info('post-migrate: %s chequera(s) creada(s) a partir de los diarios', len(rows))
        _logger.info(
            'post-migrate: se creó una chequera por diario. Los diarios que comparten una '
            'chequera física se pueden agrupar desde Contabilidad > Configuración > '
            'Contabilidad > Chequeras, acción "Unificar chequeras"; las chequeras que '
            'queden sin uso se pueden archivar.'
        )
    env.flush_all()

    cr.execute("""
        UPDATE l10n_latam_check AS chk
           SET checkbook_id = journal.checkbook_id
          FROM account_payment AS payment
          JOIN account_journal AS journal ON journal.id = payment.journal_id
          JOIN account_payment_method_line AS method_line ON method_line.id = payment.payment_method_line_id
          JOIN account_payment_method AS method ON method.id = method_line.payment_method_id
         WHERE chk.payment_id = payment.id
           AND chk.checkbook_id IS NULL
           AND chk.outstanding_line_id IS NOT NULL
           AND method.code = 'own_checks'
           AND journal.checkbook_id IS NOT NULL
    """)
    if cr.rowcount:
        _logger.info('post-migrate: chequera completada en %s cheque(s) propio(s) ya emitido(s)', cr.rowcount)
