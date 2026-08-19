# Secuencia de Cheques Propios en Diarios de Banco (`account_journal_check_sequence`)

Módulo para **Odoo 18 / 19** que añade gestión de numeración correlativa ("modo chequera") a nivel de cada diario de banco, totalmente integrado con el ecosistema de **ADHOC** (`account_payment_group`, `account_payment_pro`, `l10n_latam_check`) y el flujo estándar de Odoo.

---

## 🎯 Funcionalidades Principales

1. **Configuración por Diario de Banco (`account.journal`):**
   * Checkbox **Auto-numerar Cheques Propios** (`check_sequence_enabled`).
   * Campo **Próximo Número de Cheque** (`next_check_number`), editable en cualquier momento.
   * Campo **Dígitos del Cheque** (`check_number_padding`, por defecto 8 dígitos con ceros a la izquierda, ej. `00000001`).

2. **Propuesta Automática en Órdenes de Pago (ADHOC) y Pagos:**
   * Al crear una **Orden de Pago** (`account.payment.group`) y agregar una línea de pago con Diario de Banco y método *Cheque Propio* (`own_checks`), el número de cheque se autocompleta con el próximo correlativo del diario.
   * Compatible también con el wizard estándar de pago (`account.payment.register`).

3. **Flexibilidad Total (Saltos de secuencia / Cheques anulados):**
   * El campo número de cheque sigue siendo **100% editable** por el usuario.
   * Si el usuario modifica el número (ej. salta del `00001002` al `00001005` por rotura/anulación), el sistema respeta el número ingresado.

4. **Auto-incremento al Publicar:**
   * Al confirmar/publicar la Orden de Pago (`account.payment.group.post()` / `action_post()`), el sistema incrementa automáticamente la secuencia del diario en base al número efectivamente emitido.

---

## ⚙️ Configuración

1. Ir a **Contabilidad > Configuración > Diarios Contables**.
2. Seleccionar un diario de tipo **Banco** (ej. *Banco Galicia*, *Banco Santander*).
3. En la pestaña **Configuración Avanzada**, ubicar la sección **Chequera / Numeración de Cheques Propios**.
4. Ingresar el número del próximo cheque físico/electrónico a emitir (ej. `00001001`).
5. Guardar.

---

## 📦 Dependencias

* `account`
* `l10n_latam_check`
* Compatible con `account_payment_group` / `account_payment_pro` (ADHOC).
