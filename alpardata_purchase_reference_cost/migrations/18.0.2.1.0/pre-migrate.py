import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración 18.0.2.0.x → 18.0.2.1.0

    reference_cost en product.template pasa de computed-stored a computed NO
    almacenado. Se elimina la columna huérfana: el valor se recalcula on-the-fly
    desde product.supplierinfo.reference_cost (la fuente de verdad), así que no
    hay pérdida de datos.
    """
    if not version:
        # Instalación nueva: no hay nada que migrar.
        return

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
