# Secuencia de Cheques Propios en Diarios de Banco (`account_journal_check_sequence`)

Módulo para **Odoo 19** que añade gestión de numeración correlativa ("modo chequera") en chequeras que pueden compartir varios diarios de banco, incluso de distintas compañías, integrado con el ecosistema de **ADHOC** (`account_payment_group`, `account_payment_pro`, `l10n_latam_check`) y el flujo estándar de Odoo.

---

## 🎯 Funcionalidades Principales

1. **Chequeras (`account.checkbook`):**
   * Cada chequera tiene su **Próximo Número de Cheque** (`next_number`, admite prefijo y sufijo, ej. `E-00000100`) y sus **Dígitos del Cheque** (`padding`, por defecto 8; admite de 1 a 20).
   * Un diario de banco numera sus cheques propios si tiene una chequera asignada (`checkbook_id`). **Varios diarios pueden compartir la misma chequera** y siguen un único correlativo.
   * Si la chequera no tiene compañía, la pueden usar diarios de **distintas compañías**. Si tiene compañía, la pueden usar diarios de esa compañía y de sus sucursales (compañías hijas).
   * Desde el diario se sigue viendo y editando el próximo número y los dígitos, pero el cambio se guarda en la chequera: si la comparten varios diarios, aplica a todos. El formulario del diario avisa qué otros diarios la usan, incluso de otras compañías (se listan como "Nombre (Compañía)").
   * Una chequera **archivada** deja de sugerir números y no avanza al publicar. Una chequera en uso no se puede borrar.
   * Al crear una chequera nueva escribiendo el nombre directamente desde el diario, queda con la compañía de ese diario. Para compartirla entre compañías, borrar la compañía en el formulario de la chequera.

2. **Propuesta Automática en Órdenes de Pago (ADHOC) y Pagos:**
   * Al crear una **Orden de Pago** (`account.payment.group`) y agregar una línea de pago con Diario de Banco y método *Cheque Propio* (`own_checks`), el número de cheque se autocompleta con el próximo correlativo del diario.
   * Compatible también con el wizard estándar de pago (`account.payment.register`).
   * Al cargar varios cheques de una sola vez, cada línea recibe su propio número correlativo.
   * El próximo número libre se publica en el contexto de la One2many de cheques (campo computado `check_sequence_next_number`), así cada línea nueva nace ya numerada teniendo en cuenta las que están cargadas en pantalla y todavía no se guardaron. El contador del diario por sí solo no alcanza: no avanza hasta postear el pago.

3. **Flexibilidad Total (Saltos de secuencia / Cheques anulados):**
   * El campo número de cheque sigue siendo **100% editable** por el usuario.
   * El módulo distingue lo que autocompletó él de lo que tipeó el usuario, con el campo técnico `autofilled_check_number`. Un número **editado a mano es un ancla fija**: se respeta tal cual y las líneas siguientes encadenan a partir de él. Si el usuario salta del `00001002` al `00001050` porque arrancó otra chequera, la línea siguiente pasa a `00001051`.
   * Las líneas autocompletadas se recalculan en cada pasada, así que se acomodan solas a esos saltos y no quedan repitiendo un número.
   * Un número duplicado **tipeado por el usuario** no se reescribe: si fue un error, lo marca el control de duplicados (ver punto 5). Es preferible eso a cambiarle en silencio un valor que escribió a mano.

4. **Auto-incremento al Publicar:**
   * Al confirmar/publicar el pago (`action_post()`), el módulo incrementa la secuencia de la chequera a partir del número **más alto** efectivamente emitido.
   * El contador **nunca retrocede**: postear un pago viejo con un número inferior al ya alcanzado no reposiciona la secuencia hacia atrás (evita sugerir números duplicados). Sí se acepta un cambio de serie, es decir un número con otro prefijo o sufijo.
   * La escritura sobre la chequera se hace con `sudo()`, para que un usuario de Facturación (sin permiso de escritura sobre `account.checkbook`) pueda postear pagos sin errores de acceso.
   * Antes de publicar se toma un lock exclusivo sobre la chequera (un `UPDATE` que no cambia el valor). Dos pagos publicados en paralelo sobre la misma chequera, aunque sean de diarios o compañías distintos, se serializan: el segundo espera y, cuando el primero confirma, Odoo lo reintenta y ya ve el número emitido. Se usa sin `NOWAIT` a propósito, para que el segundo pago espere en lugar de fallar.

5. **Control de Números Duplicados:**
   * Al publicar, cada cheque guarda la chequera que lo emitió (`l10n_latam.check.checkbook_id`).
   * Si un número ya fue emitido en la misma chequera, desde cualquier diario o compañía, el pago muestra el aviso rojo de cheques mientras se carga y **no deja publicar**. Lo mismo si el número se repite dentro del mismo pago, o entre varios pagos que se confirman juntos en un lote (batch).
   * Cuentan los cheques de pagos publicados, incluidos los anulados (ese número ya se usó en papel). No cuentan los pagos en borrador ni los cancelados.
   * La búsqueda de duplicados usa `sudo()`: el aviso nombra el otro pago o diario aunque pertenezca a otra compañía y el usuario no tenga acceso a verlo. Es intencional, porque compartir la chequera entre compañías es una decisión deliberada de la configuración.
   * Odoo trae de fábrica un índice único, pero es por diario: no detecta duplicados entre diarios que comparten chequera.

6. **Asistente "Unificar chequeras":**
   * Desde la lista de chequeras, seleccionar varias y usar la acción **Unificar chequeras**.
   * Propone como destino la chequera con más diarios y como próximo número el más alto de todas; los dos se pueden cambiar.
   * Propone como compañía resultante la compañía común de los diarios o, si son de distintas sucursales, la compañía padre común más cercana; queda vacía solo si los diarios no tienen ninguna compañía en común.
   * Pasa a la chequera destino todos los diarios **y los cheques ya emitidos**, y archiva las demás. Si la chequera destino estaba archivada, se reactiva.
   * Informa los números que ya estaban repetidos en la historia; no los corrige ni impide unificar.

---

## ⚙️ Configuración

1. Ir a **Contabilidad > Configuración > Contabilidad > Chequeras** y crear una chequera con el número del próximo cheque físico/electrónico a emitir (ej. `00001001`). Si la van a usar diarios de varias compañías, dejar la compañía vacía.
2. En cada diario de banco que emite de esa chequera (**Configuración Avanzada > Chequera / Numeración de Cheques Propios**), elegir la chequera. También se puede crear desde ahí escribiendo el nombre; en ese caso la chequera nace con la compañía del diario (para compartirla, borrarla después en el formulario de la chequera).
3. Guardar.

El menú **Chequeras** es visible solo para el grupo `account.group_account_manager`; los usuarios de `account.group_account_readonly` tienen acceso de solo lectura al modelo.

### Puesta en marcha después de actualizar desde 19.0.1.2.0

La actualización crea una chequera por cada diario que tenía la numeración activa, con su número actual. Si varias sucursales emiten de la misma chequera física:

1. Ir a **Chequeras**, seleccionar las chequeras de esas sucursales y usar **Unificar chequeras**.
2. Revisar el próximo número propuesto y el aviso de números repetidos, si aparece.
3. Confirmar.

---

## 🔗 Relación con `account_check_printing` (Odoo estándar)

Odoo trae su propia numeración de chequera para el método **Check Printing**, basada en `ir.sequence` (`check_manual_sequencing`, `check_sequence_id`, `check_next_number`), pero **no contempla los cheques LATAM** (diferidos, echeqs, carga manual del número): ese es el motivo por el que existe este módulo.

El alcance acá es exclusivamente el método **Cheque Propio** (`own_checks`) de `l10n_latam_check`. Las dos numeraciones son independientes y no se pisan: si además se usara `check_printing` en el mismo diario, ese método sigue gobernado por la secuencia nativa de Odoo.

---

## 🚚 Migración desde 18.0

`migrations/19.0.1.0.0/post-migrate.py` sanea los datos que vienen de la versión 18.0. No hay cambios de esquema; el script:

1. Apaga `check_sequence_enabled` en los diarios que no son de banco (en 18.0 el campo nacía en `True` para todos, aunque la vista solo lo muestra en bancos). Los diarios de banco conservan su valor.
2. Normaliza `next_check_number` (vacíos y espacios sobrantes) y `check_number_padding` (nulos o fuera del rango 1–20).

Es idempotente y no corre en instalaciones nuevas.

Como en 18.0 el flag de numeración nacía en `True`, al actualizar se crea una chequera por cada diario de banco (ver abajo), aunque en muchos no se haya usado la numeración en la práctica. Las chequeras que queden sin uso se pueden archivar.

### 19.0.1.2.0 → 19.0.1.3.0

`migrations/19.0.1.3.0/post-migrate.py`:

1. Crea una chequera por cada diario de banco con la numeración activa y le copia el próximo número, los dígitos y la compañía. El nombre de la chequera es el nombre del diario, en el idioma de la compañía.
2. Completa la chequera emisora en los cheques propios ya emitidos, para que el control de duplicados cubra la historia.

No fusiona chequeras (para eso está el asistente) y deja en `account_journal` las columnas viejas como respaldo. Es idempotente. El log del script recuerda usar el asistente **Unificar chequeras** para agrupar las que comparten chequera física.

---

## 📦 Dependencias

* `account`
* `l10n_latam_check`
* Compatible con `account_payment_group` / `account_payment_pro` (ADHOC).
