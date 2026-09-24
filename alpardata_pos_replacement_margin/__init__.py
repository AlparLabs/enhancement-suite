from . import models
from . import report


def pre_init_hook(env):
    """Crea las columnas en 0: las órdenes anteriores a la instalación no se recalculan."""
    env.cr.execute("""
        ALTER TABLE pos_order_line
            ADD COLUMN IF NOT EXISTS replacement_cost_unit double precision DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replacement_margin numeric DEFAULT 0;
        ALTER TABLE pos_order
            ADD COLUMN IF NOT EXISTS replacement_margin numeric DEFAULT 0;
    """)
