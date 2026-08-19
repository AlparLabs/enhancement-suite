# Acceso por Almacén

Limita la visibilidad de transferencias y órdenes de compra al almacén asignado
a cada usuario, sin impedir las transferencias entre almacenes.

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

## Fuera de alcance

Líneas de orden de compra, reporte de compras, existencias, ajustes de
inventario, ventas y POS.
