MANAGER_GROUP_XMLIDS = (
    'stock.group_stock_manager',
    'purchase.group_purchase_manager',
)


def post_init_hook(env):
    """Exime del filtro por almacén a los gerentes que ya existían.

    El módulo falla cerrado: sin almacenes cargados un usuario no ve ningún
    documento con almacén. Sin esto, instalar en producción dejaría a la
    gerencia sin acceso hasta configurar usuario por usuario.
    """
    group_all = env.ref(
        'stock_warehouse_user_access.group_warehouse_access_all',
        raise_if_not_found=False,
    )
    if not group_all:
        return

    manager_groups = env['res.groups']
    for xmlid in MANAGER_GROUP_XMLIDS:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            manager_groups |= group
    if not manager_groups:
        return

    users = env['res.users'].sudo().search([
        ('share', '=', False),
        ('groups_id', 'in', manager_groups.ids),
    ])
    if users:
        group_all.sudo().write({
            'users': [(4, user.id) for user in users],
        })
