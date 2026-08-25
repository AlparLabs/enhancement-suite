import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración 19.0.2.0.x → 19.0.2.1.0

    1. reference_cost en product.template pasa de computed-stored a computed NO
       almacenado. Se elimina la columna huérfana: el valor se recalcula
       on-the-fly desde product.supplierinfo.reference_cost (la fuente de
       verdad), así que no hay pérdida de datos.

    2. Se elimina el wizard de actualización masiva
       (product.reference.cost.mass.update). Se dropea su tabla huérfana.
    """
    if not version:
        # Instalación nueva: no hay nada que migrar.
        return

    # ── 1. reference_cost deja de estar almacenado ───────────────────────────
    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'reference_cost'
    """)
    if cr.fetchone():
        _logger.info(
            'pre-migrate: reference_cost pasa a no-almacenado. '
            'Eliminando columna huérfana product_template.reference_cost.'
        )
        cr.execute(
            'ALTER TABLE product_template DROP COLUMN IF EXISTS reference_cost'
        )
    else:
        _logger.info(
            'pre-migrate: columna product_template.reference_cost no existe, '
            'nada que hacer.'
        )

    # ── 2. Tabla huérfana del wizard eliminado ───────────────────────────────
    cr.execute("SELECT to_regclass('product_reference_cost_mass_update')")
    if cr.fetchone()[0]:
        _logger.info(
            'pre-migrate: eliminando tabla huérfana '
            '"product_reference_cost_mass_update".'
        )
        cr.execute(
            'DROP TABLE IF EXISTS product_reference_cost_mass_update CASCADE'
        )
