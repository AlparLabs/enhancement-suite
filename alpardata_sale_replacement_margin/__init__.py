from . import models
from . import report


def pre_init_hook(env):
    """Crea las columnas en 0: los pedidos anteriores a la instalación no se
    recalculan (quedarían con el costo de hoy, que es el dato engañoso)."""
    env.cr.execute("""
        ALTER TABLE sale_order_line
            ADD COLUMN IF NOT EXISTS replacement_cost_unit double precision DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replacement_cost_fallback boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS replacement_margin double precision DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replacement_margin_percent double precision DEFAULT 0;
        ALTER TABLE sale_order
            ADD COLUMN IF NOT EXISTS replacement_margin numeric DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replacement_margin_percent double precision DEFAULT 0;
    """)
