# Secuencia de Cheques Propios en Diarios de Banco (`account_journal_check_sequence`)

Módulo para **Odoo 19** que añade gestión de numeración correlativa ("modo chequera") a nivel de cada diario de banco, integrado con el ecosistema de **ADHOC** (`account_payment_group`, `account_payment_pro`, `l10n_latam_check`) y el flujo estándar de Odoo.

---

## 🎯 Funcionalidades Principales

1. **Configuración por Diario de Banco (`account.journal`):**
   * Checkbox **Auto-numerar Cheques Propios** (`check_sequence_enabled`), desactivado por defecto.
   * Campo **Próximo Número de Cheque** (`next_check_number`), editable en cualquier momento.
   * Campo **Dígitos del Cheque** (`check_number_padding`, por defecto 8 dígitos con ceros a la izquierda, ej. `00000001`; admite de 1 a 20).

2. **Propuesta Automática en Órdenes de Pago (ADHOC) y Pagos:**
   * Al crear una **Orden de Pago** (`account.payment.group`) y agregar una línea de pago con Diario de Banco y método *Cheque Propio* (`own_checks`), el número de cheque se autocompleta con el próximo correlativo del diario.
   * Compatible también con el wizard estándar de pago (`account.payment.register`).
   * Al cargar varios cheques de una sola vez, cada línea recibe su propio número correlativo.

3. **Flexibilidad Total (Saltos de secuencia / Cheques anulados):**
   * El campo número de cheque sigue siendo **100% editable** por el usuario.
   * Si el usuario modifica el número (ej. salta del `00001002` al `00001005` por rotura/anulación), el sistema respeta el número ingresado y encadena a partir de él.

4. **Auto-incremento al Publicar:**
   * Al confirmar/publicar el pago (`action_post()`), el módulo incrementa la secuencia del diario a partir del número **más alto** efectivamente emitido.
   * El contador **nunca retrocede**: postear un pago viejo con un número inferior al ya alcanzado no reposiciona la secuencia hacia atrás (evita sugerir números duplicados). Sí se acepta un cambio de serie, es decir un número con otro prefijo o sufijo.
   * La escritura sobre el diario se hace con `sudo()`, para que un usuario de Facturación (sin permiso de escritura sobre `account.journal`) pueda postear pagos sin errores de acceso.
   * El avance del contador toma un lock exclusivo sobre la fila del diario (`SELECT ... FOR UPDATE`). Dos pagos publicados en paralelo se serializan: el segundo espera y recalcula sobre el valor ya actualizado, en vez de emitir el mismo número. Se usa sin `NOWAIT` a propósito, para que el segundo pago espere en lugar de fallar.

---

## ⚙️ Configuración

1. Ir a **Contabilidad > Configuración > Diarios Contables**.
2. Seleccionar un diario de tipo **Banco** (ej. *Banco Galicia*, *Banco Santander*).
3. En la pestaña **Configuración Avanzada**, ubicar la sección **Chequera / Numeración de Cheques Propios**.
4. Activar **Auto-numerar Cheques Propios** e ingresar el número del próximo cheque físico/electrónico a emitir (ej. `00001001`).
5. Guardar.

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

---

## 📦 Dependencias

* `account`
* `l10n_latam_check`
* Compatible con `account_payment_group` / `account_payment_pro` (ADHOC).
