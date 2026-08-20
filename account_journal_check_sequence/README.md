# Secuencia de Cheques Propios en Diarios de Banco (`account_journal_check_sequence`)

Módulo para **Odoo 18 / 19** que añade gestión de numeración correlativa ("modo chequera") a nivel de cada diario de banco, totalmente integrado con el ecosistema de **ADHOC** (`account_payment_group`, `account_payment_pro`, `l10n_latam_check`) y el flujo estándar de Odoo.

---

## 🎯 Funcionalidades Principales

1. **Configuración por Diario de Banco (`account.journal`):**
   * Checkbox **Auto-numerar Cheques Propios** (`check_sequence_enabled`), desactivado por defecto: hay que habilitarlo diario por diario.
   * Campo **Próximo Número de Cheque** (`next_check_number`), editable en cualquier momento.
   * Campo **Dígitos del Cheque** (`check_number_padding`, por defecto 8 dígitos con ceros a la izquierda, ej. `00000001`). **Mínimo 8**: `l10n_latam.check._onchange_name` hace `name.zfill(8)`, así que un padding menor dejaría el contador desalineado con el número guardado en el cheque.

2. **Alcance: ambos flujos de cheque propio:**
   * `own_checks` (localización, `l10n_latam_check`): numera las líneas de la pestaña **Cheques** (`l10n_latam_new_check_ids`).
   * `check_printing` (flujo estándar): numera el campo `check_number` del pago. Odoo ya trae numeración nativa para este método (`check_manual_sequencing` / `check_next_number` / `check_sequence_id`, respaldada por un `ir.sequence` real); **una constraint impide activar ambas sobre el mismo diario**, así que este módulo sólo actúa si la nativa está apagada.

3. **Propuesta Automática en Órdenes de Pago (ADHOC) y Pagos:**
   * Al crear una **Orden de Pago** (`account.payment.group`) y agregar una línea de pago con Diario de Banco y método *Cheque Propio* (`own_checks`), el número de cheque se autocompleta con el próximo correlativo del diario.
   * Compatible también con el wizard estándar de pago (`account.payment.register`).

4. **Flexibilidad Total (Saltos de secuencia / Cheques anulados):**
   * El campo número de cheque sigue siendo **100% editable** por el usuario.
   * Si el usuario modifica el número (ej. salta del `00001002` al `00001005` por rotura/anulación), el sistema respeta el número ingresado.
   * Si se cambia el diario del pago, los números que había puesto el módulo se recalculan con la chequera nueva; los cargados a mano se respetan.

5. **Auto-incremento al Publicar:**
   * Al confirmar/publicar el pago (`action_post()`), el sistema incrementa la secuencia del diario en base al **mayor** número efectivamente emitido en ese pago.
   * La secuencia **nunca retrocede**: reemitir un cheque anterior, o volver a publicar un pago que ya avanzó el contador, no altera la chequera.
   * El diario se bloquea (`SELECT ... FOR UPDATE`) mientras se calcula el próximo número, para que dos pagos publicados en paralelo no consuman el mismo valor.

---

---

## ⚠️ Limitación conocida

El número se **sugiere** al armar el pago y se **consume** recién al publicarlo. Dos usuarios que preparan pagos al mismo tiempo van a ver sugerido el mismo número; el conflicto aparece al validar, contra el índice único `l10n_latam_check_unique` sobre `(name, payment_method_line_id) WHERE outstanding_line_id IS NOT NULL`. Para reserva estricta habría que migrar `next_check_number` a un `ir.sequence` real.

---

## ⚙️ Configuración

1. Ir a **Contabilidad > Configuración > Diarios Contables**.
2. Seleccionar un diario de tipo **Banco** (ej. *Banco Galicia*, *Banco Santander*).
3. En la pestaña **Configuración Avanzada**, ubicar la sección **Chequera / Numeración de Cheques Propios**.
4. Activar **Auto-numerar Cheques Propios** e ingresar el número del próximo cheque físico/electrónico a emitir (ej. `00001001`).
5. Guardar.

---

## 📦 Dependencias

* `account`
* `l10n_latam_check`
* Compatible con `account_payment_group` / `account_payment_pro` (ADHOC).
