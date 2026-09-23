# Acceso por Almacén

Limita la visibilidad de transferencias, órdenes de compra, reportes,
reabastecimiento y ajustes de inventario al almacén asignado a cada usuario, sin
impedir las transferencias entre almacenes.

## Configuración

En Ajustes → Usuarios, pestaña "Permisos de acceso", sección "Acceso por Almacén":

- **Almacenes permitidos**: almacenes cuyos documentos ve el usuario.
- **Almacén por defecto**: el que se propone al crear una transferencia o una
  orden de compra. Debe estar dentro de los permitidos.
- **Ver todos los almacenes**: exime al usuario del filtro.

## Comportamiento

- **Transferencias**: el usuario ve un albarán si el tipo de operación, la
  ubicación origen o la ubicación destino pertenecen a alguno de sus almacenes.
  Por eso una transferencia entre almacenes es visible desde las dos puntas.
- **Compras**: ve solo las órdenes cuyo "Entregar a" apunta a un almacén suyo.
  Las órdenes sin almacén (servicios, dropship) son visibles para todos.
- **Desplegables**: el tipo de operación de las transferencias, el "Entregar a"
  de las compras y el panel Resumen de Inventario listan solo los almacenes del
  usuario.
- **Ajustes** (Inventario físico, Desechos) y **Reportes → Ubicaciones**: solo
  los quants y desechos cuya ubicación pertenece a un almacén del usuario. Los
  quants en ubicaciones de tránsito sin almacén no se muestran.
- **Reabastecimiento**: solo los puntos de pedido de sus almacenes.
- **Reportes → Historial y Análisis de movimientos**: los movimientos cuyo
  origen, destino o tipo de operación pertenecen a un almacén del usuario (un
  movimiento entre almacenes se ve desde las dos puntas).
- **Reportes → Existencias**: las cantidades se calculan solo sobre sus
  almacenes. Si filtra por un almacén ajeno, ve cero.

### Transferencias y compras vs. reportes y ajustes

Son dos mecanismos distintos a propósito:

- Transferencias y compras se restringen con **reglas de registro**: el usuario
  no puede leerlas ni por API.
- Reportes, reabastecimiento y ajustes se restringen **solo en la interfaz**: el
  dominio se agrega a la acción que abre el menú (`ir.actions.act_window.
  _get_action_dict` y las acciones Python de `stock.quant`). Los registros
  siguen existiendo y el core los sigue viendo; poner reglas de registro en
  quants, movimientos o puntos de pedido rompe procesos del core (reservas,
  cadenas de movimientos entre almacenes y la generación de puntos de pedido
  del reabastecimiento, que choca con la constraint única).

## Advertencias

- **Falla cerrado.** Un usuario sin almacenes cargados y sin el permiso "Ver
  todos los almacenes" no ve ningún documento que tenga almacén. Al instalar, el
  módulo le otorga ese permiso a quienes ya sean gerente de inventario o
  administrador de compras; el resto hay que configurarlo a mano.
- **El filtro de los desplegables es de interfaz, no de seguridad.** Vía
  importación o API se puede apuntar a otro almacén; el documento resultante
  simplemente desaparecerá de la vista del usuario por las reglas de registro.
- El módulo modifica el contexto de la acción stock.stock_picking_type_action.
  Ese cambio persiste después de desinstalar.
- **El filtro de reportes y ajustes es de interfaz.** Aplica a lo que se abre
  desde el menú. Los accesos contextuales que reescriben el dominio de la acción
  (por ejemplo, el botón "Entradas/Salidas" de la ficha de producto) muestran
  lo que el core decida para ese contexto.
- **Reportes y Reabastecimiento son de gerente en el core.** Un usuario con
  solo "Usuario" de Inventario no ve esos menús. Para que un encargado de
  sucursal los vea filtrados, tiene que ser gerente de inventario *sin* el
  permiso "Ver todos los almacenes" (al instalar, el módulo se lo da a los
  gerentes existentes: hay que quitárselo).

## Fuera de alcance

Líneas de orden de compra, reporte de compras, valoración de inventario
(stock_account), pronóstico (report.stock.quantity), ventas y POS.
