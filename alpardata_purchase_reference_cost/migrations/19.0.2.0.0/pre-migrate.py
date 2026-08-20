import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración 19.0.1.0.0 → 19.0.2.0.0

    Cambio de arquitectura:
    - v1: reference_cost en product.template como campo company_dependent (almacenado en JSON)
          + historial en product.cost.history
    - v2: reference_cost en product.supplierinfo (campo directo float)
          + reference_cost en product.template como campo computed desde seller_ids
          + historial en product.supplierinfo.cost.history

    Acciones:
    1. Lee los reference_cost existentes en product_template (columna JSON).
    2. Por cada producto con reference_cost > 0 y proveedor principal, crea un
       supplierinfo con ese valor (el ORM propagará el campo computed).
    3. Elimina la columna reference_cost de product_template (será recreada como
       double precision por el ORM al final del upgrade).
    4. Elimina la tabla product_cost_history (modelo removido en v2).
    """
    if not version:
        # Instalación nueva: no hay nada que migrar
        return

    _logger.info('pre-migrate: iniciando migración 19.0.1.0.0 → 19.0.2.0.0')

    # ── 1. Leer reference_cost existentes en product_template ────────────────
    cr.execute("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'product_template'
          AND column_name = 'reference_cost'
    """)
    row = cr.fetchone()

    if row:
        col_type = row[0].lower()
        _logger.info(
            'pre-migrate: columna product_template.reference_cost encontrada (tipo: %s)',
            col_type,
        )

        if col_type in ('json', 'jsonb'):
            # Columna company_dependent: extraer valores por (product_id, company_id)
            # El JSON tiene la forma: {"company_id": value, ...} o {1: value}
            _migrate_company_dependent_values(cr)
        elif col_type in ('double precision', 'numeric', 'real', 'float'):
            # Columna float simple: migrar a supplierinfo
            _migrate_float_values(cr)

        # Eliminar la columna para que Odoo la recree como computed stored (float)
        _logger.info('pre-migrate: eliminando columna product_template.reference_cost')
        cr.execute('ALTER TABLE product_template DROP COLUMN IF EXISTS reference_cost')
    else:
        _logger.info(
            'pre-migrate: columna product_template.reference_cost no encontrada, '
            'se creará nueva durante el upgrade.'
        )

    # ── 2. Eliminar tabla product_cost_history (modelo removido) ─────────────
    cr.execute("SELECT to_regclass('product_cost_history')")
    if cr.fetchone()[0]:
        _logger.info('pre-migrate: eliminando tabla product_cost_history')
        cr.execute('DROP TABLE IF EXISTS product_cost_history CASCADE')
    else:
        _logger.info('pre-migrate: tabla product_cost_history no existe, omitiendo.')

    _logger.info('pre-migrate: migración 19.0.1.0.0 → 19.0.2.0.0 completada.')


def _migrate_company_dependent_values(cr) -> None:
    """
    Extrae valores de la columna JSONB company_dependent y crea supplierinfo records.
    El JSON tiene la forma: {company_id_str: float_value, ...}
    """
    cr.execute("""
        SELECT
            pt.id AS product_tmpl_id,
            kv.key::integer AS company_id,
            kv.value::float AS reference_cost
        FROM product_template pt,
             jsonb_each_text(pt.reference_cost::jsonb) AS kv(key, value)
        WHERE pt.reference_cost IS NOT NULL
          AND pt.reference_cost::text NOT IN ('null', '{}', '')
    """)
    rows = cr.fetchall()

    if not rows:
        _logger.info('pre-migrate: no se encontraron valores company_dependent para migrar.')
        return

    _logger.info(
        'pre-migrate: encontrados %d valores de reference_cost para migrar a supplierinfo.',
        len(rows),
    )
    _create_supplierinfo_records(cr, rows)


def _migrate_float_values(cr) -> None:
    """
    Extrae valores de una columna float simple y los asocia a la empresa actual.
    """
    # For a simple float, pick the first (main) company
    cr.execute("""
        SELECT
            pt.id,
            (SELECT id FROM res_company ORDER BY id LIMIT 1) AS company_id,
            pt.reference_cost
        FROM product_template pt
        WHERE pt.reference_cost IS NOT NULL
          AND pt.reference_cost > 0
    """)
    rows = cr.fetchall()

    if not rows:
        _logger.info('pre-migrate: no se encontraron valores float para migrar.')
        return

    _logger.info(
        'pre-migrate: encontrados %d valores float de reference_cost para migrar.',
        len(rows),
    )
    _create_supplierinfo_records(cr, rows)


def _create_supplierinfo_records(cr, rows) -> None:
    """
    Para cada (product_tmpl_id, company_id, reference_cost):
    - Busca el proveedor principal vigente del producto.
    - Si existe, crea un nuevo supplierinfo con el reference_cost preservado.
    """
    created = 0
    skipped = 0

    for product_tmpl_id, company_id, reference_cost in rows:
        if not reference_cost or reference_cost <= 0:
            continue

        # Buscar proveedor principal vigente
        cr.execute("""
            SELECT id, partner_id, price, sequence,
                   min_qty, delay, currency_id, product_uom_id
            FROM product_supplierinfo
            WHERE product_tmpl_id = %s
              AND (company_id IS NULL OR company_id = %s)
              AND (date_end IS NULL OR date_end >= CURRENT_DATE)
            ORDER BY sequence ASC
            LIMIT 1
        """, (product_tmpl_id, company_id))
        seller = cr.fetchone()

        if not seller:
            _logger.debug(
                'pre-migrate: producto id=%s, company=%s no tiene proveedor principal. '
                'El reference_cost %.2f no se puede migrar a supplierinfo.',
                product_tmpl_id, company_id, reference_cost,
            )
            skipped += 1
            continue

        (seller_id, partner_id, price, sequence,
         min_qty, delay, currency_id, product_uom_id) = seller

        cr.execute("""
            INSERT INTO product_supplierinfo
                (product_tmpl_id, partner_id, company_id, reference_cost,
                 price, date_start, sequence,
                 min_qty, delay, currency_id, product_uom_id,
                 create_date, write_date, create_uid, write_uid)
            VALUES
                (%s, %s, %s, %s,
                 %s, CURRENT_DATE, %s,
                 %s, %s, %s, %s,
                 NOW(), NOW(), 1, 1)
        """, (
            product_tmpl_id, partner_id, company_id, reference_cost,
            price or 0.0, sequence,
            min_qty or 0.0, delay or 1, currency_id, product_uom_id,
        ))
        created += 1

    _logger.info(
        'pre-migrate: supplierinfo records creados: %d | omitidos (sin proveedor): %d',
        created, skipped,
    )
