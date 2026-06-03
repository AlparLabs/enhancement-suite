import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración v1.x → v2.0.0

    1. Elimina la columna reference_cost de product_template si existe con
       tipo JSON (era company_dependent=True). Odoo la recreará como
       double precision (computed stored).

    2. Elimina tablas huérfanas de modelos removidos en v2.0.0:
       - product_cost_history
       - product_reference_cost_mass_update (wizard)
       - product_supplier_pricelist_import (wizard)
       - product_supplier_pricelist_import_line (wizard)
    """
    if not version:
        # Instalación nueva: no hay nada que migrar
        return

    # ── 1. Columna reference_cost en product_template ─────────────────────────
    cr.execute("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'reference_cost'
    """)
    row = cr.fetchone()
    if row:
        _logger.info(
            'pre-migrate: reference_cost en product_template es tipo "%s". '
            'Eliminando para que Odoo la recree como double precision (computed stored).',
            row[0],
        )
        cr.execute('ALTER TABLE product_template DROP COLUMN reference_cost')
    else:
        _logger.info(
            'pre-migrate: reference_cost no existe en product_template, '
            'se creará nueva en el upgrade.'
        )

    # ── 2. Tablas huérfanas de modelos eliminados ─────────────────────────────
    orphaned_tables = [
        'product_cost_history',
        'product_reference_cost_mass_update',
        'product_supplier_pricelist_import',
        'product_supplier_pricelist_import_line',
    ]
    for table in orphaned_tables:
        cr.execute("SELECT to_regclass(%s)", (table,))
        if cr.fetchone()[0]:
            _logger.info('pre-migrate: eliminando tabla huérfana "%s".', table)
            cr.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
