import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración 18.0.1.0.0 → 19.0.1.0.0

    El esquema no cambia (los tres campos del diario ya existían en 18.0), así
    que esta migración es solo de saneamiento de datos:

    1. `check_sequence_enabled` pasó de default=True a default=False. Los
       diarios que no son de banco quedaron con el flag activo en 18.0 sin que
       tuviera ningún efecto (la vista lo oculta). Se apaga para que el estado
       almacenado refleje lo que el usuario realmente ve y usa. Los diarios de
       banco conservan su valor: no cambiamos el comportamiento vigente.
    2. Se normalizan `next_check_number` (espacios sobrantes / vacíos) y
       `check_number_padding` (nulos o fuera del rango admitido), que ahora
       tiene una restricción de 1 a 20 dígitos.
    El script es idempotente: se puede volver a ejecutar sin efectos adicionales.
    """
    if not version:
        # Instalación nueva: no hay datos previos que sanear.
        return

    _logger.info('post-migrate: saneando datos de account_journal_check_sequence')

    # ── 1. Apagar el flag en diarios que no son de banco ─────────────────────
    cr.execute("""
        UPDATE account_journal
           SET check_sequence_enabled = FALSE
         WHERE check_sequence_enabled IS TRUE
           AND type != 'bank'
    """)
    if cr.rowcount:
        _logger.info(
            'post-migrate: auto-numeración desactivada en %s diario(s) que no son de banco',
            cr.rowcount,
        )

    cr.execute("""
        UPDATE account_journal
           SET check_sequence_enabled = FALSE
         WHERE check_sequence_enabled IS NULL
    """)

    # ── 2. Normalizar el número y el padding ─────────────────────────────────
    cr.execute("""
        UPDATE account_journal
           SET next_check_number = '00000001'
         WHERE type = 'bank'
           AND (next_check_number IS NULL OR btrim(next_check_number) = '')
    """)
    if cr.rowcount:
        _logger.info(
            'post-migrate: %s diario(s) de banco sin próximo número, inicializados en 00000001',
            cr.rowcount,
        )

    cr.execute("""
        UPDATE account_journal
           SET next_check_number = btrim(next_check_number)
         WHERE next_check_number IS NOT NULL
           AND next_check_number != btrim(next_check_number)
    """)

    cr.execute("""
        UPDATE account_journal
           SET check_number_padding = 8
         WHERE check_number_padding IS NULL
            OR check_number_padding < 1
            OR check_number_padding > 20
    """)
    if cr.rowcount:
        _logger.info(
            'post-migrate: %s diario(s) con cantidad de dígitos inválida, ajustados a 8',
            cr.rowcount,
        )
