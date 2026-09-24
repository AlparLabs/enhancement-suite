from . import models
from . import wizard


def post_init_hook(env):
    """Al instalar, toma la foto de precios y la marca como impresa para que no
    queden todos los productos como etiqueta pendiente."""
    watch = env['product.price.watch'].sudo()
    for company in env['res.company'].search([]):
        watches = watch._refresh_company(company)
        for rec in watches:
            rec.label_printed_price = rec.shelf_price
