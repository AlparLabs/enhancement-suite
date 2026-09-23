# Chequeras compartidas entre diarios — Diseño

**Fecha:** 2026-09-23
**Repo/rama destino:** enhancement-suite / 19.0
**Módulo:** `account_journal_check_sequence` (19.0.1.2.0 → 19.0.1.3.0)

## Objetivo

Hoy la numeración de cheques propios vive dentro de cada diario de banco
(`check_sequence_enabled`, `next_check_number`, `check_number_padding` en
`account.journal`), así que cada diario tiene su propio contador (relación
1:1). Un cliente tiene sucursales que emiten cheques de **una misma chequera
física** desde diarios distintos, que pueden estar en la misma compañía o en
compañías distintas. Necesitan que todos esos diarios consuman un único
contador, sin números duplicados aunque posteen al mismo tiempo.

La solución es sacar el contador del diario a un modelo propio,
`account.checkbook`, y que los diarios lo referencien (relación N:1).

## Decisiones tomadas

- **Modelo propio, no `ir.sequence`.** El módulo espía el próximo número
  sin consumirlo, acepta que el usuario salte números a mano, reposiciona el
  contador en el número más alto emitido, nunca retrocede e infiere el
  prefijo/sufijo de lo que tipea el usuario. `ir.sequence` no modela nada de
  eso: habría que construirlo encima y además convivir con dos fuentes de
  verdad para el prefijo. Además `check_sequence_id` ya lo usa
  `account_check_printing`.
- **Tampoco un "diario maestro".** Descartado porque un diario pasaría a ser
  dueño del contador de los demás y en multicompañía quedaría atado a una
  compañía.
- **Una sola chequera por diario.** Esa chequera puede estar compartida con
  otros diarios. Un diario no tiene varias chequeras a la vez.
- **Sirve entre compañías.** Si `company_id` está vacío, la chequera se
  puede compartir entre compañías.
- **Tener chequera asignada equivale a tener la numeración activa.** Se
  elimina el booleano como fuente de verdad.
- **La migración no fusiona chequeras.** Crea una chequera por cada diario
  habilitado. La unificación es manual y queda documentada.
- **Las columnas viejas no se borran** en esta versión y quedan como
  respaldo.

## Modelo `account.checkbook`

`_description = 'Chequera'`, `_order = 'name'`.

| Campo | Tipo | Notas |
|---|---|---|
| `name` | Char, required | Ej. "Galicia – Serie B" |
| `next_number` | Char, `copy=False`, default `'00000001'` | Próximo número a sugerir; admite prefijo/sufijo (`E-00000100`) |
| `padding` | Integer, default `8` | Constraint 1..20 (`MAX_CHECK_NUMBER_PADDING`) |
| `company_id` | Many2one `res.company`, opcional | Vacío = compartible entre compañías |
| `journal_ids` | One2many `account.journal` / `checkbook_id` | Solo de lectura en la UI |
| `active` | Boolean, default `True` | Se archiva una chequera agotada |

**Lógica que se mueve desde `account.journal`, sin cambios de
comportamiento** (se reemplaza `next_check_number` por `next_number` y
`check_number_padding` por `padding`):

- `CHECK_NUMBER_RE`, `DEFAULT_CHECK_NUMBER_PADDING`,
  `MAX_CHECK_NUMBER_PADDING` (constantes de módulo)
- `_parse_check_number`, `_format_check_number`
- `_get_next_check_number_formatted`, `_calculate_next_number`
- `_peek_check_numbers`, `_get_highest_check_number`
- `_is_check_number_ahead`
- `_lock_and_read_next_check_number` → `SELECT next_number FROM
  account_checkbook WHERE id = %s FOR UPDATE` (sin `NOWAIT`, igual que hoy)
- `_increment_check_number` → escribe con `sudo()`. Antes de avanzar el
  contador valida `active`: una chequera archivada no avanza.

Como el lock ahora es sobre la fila de la chequera, **serializa también los
posteos de diarios y compañías distintos** que comparten chequera.

## Cambios en `account.journal`

- `checkbook_id`: Many2one `account.checkbook`, `ondelete='restrict'`,
  `copy=False`, `check_company=False` (la compatibilidad de compañía se
  valida con la constraint de abajo, porque la chequera puede no tener
  compañía).
- `check_sequence_enabled`: pasa a ser un campo computado no almacenado =
  `bool(checkbook_id) and checkbook_id.active`. Se mantiene para no romper
  referencias externas.
- `next_check_number`: `related='checkbook_id.next_number'`,
  `readonly=False`.
- `check_number_padding`: `related='checkbook_id.padding'`,
  `readonly=False`.
- `checkbook_shared_journal_ids`: campo computado no almacenado con los
  otros diarios que usan la misma chequera (sin incluir el diario actual).
  Se usa para el aviso en la vista.
- Constraint `_check_checkbook_company`: si `checkbook_id.company_id` está
  definido y es distinto de `journal.company_id`, lanza `ValidationError`.
  La misma validación va en `account.checkbook` sobre `company_id` y
  `journal_ids`, para que cambiarle la compañía a una chequera en uso no
  deje combinaciones inválidas.
- Se eliminan del diario los métodos de secuencia (ahora están en la
  chequera) y la constraint de padding.

## Cambios en los consumidores

- `account.check.sequence.mixin`:
  - `_check_sequence_journal()` → `_check_sequence_checkbook()`. Devuelve
    `journal_id.checkbook_id` si la chequera está activa y el pago es
    `own_checks`. Si no, devuelve `account.checkbook` vacío.
  - `@api.depends` de `_compute_check_sequence_next_number` →
    `journal_id.checkbook_id.next_number`, `journal_id.checkbook_id.active`
    (se agrega `journal_id.checkbook_id`).
  - `_apply_check_sequence_suggestion` usa la chequera.
- `account.check.sequence.line.mixin._get_next_check_number_for_line`:
  usa `parent._check_sequence_checkbook()`.
- `account.payment` (posteo): `checkbook._increment_check_number(
  checkbook._get_highest_check_number(used_numbers))`.
- `l10n_latam_check.py` y el wizard `account_payment_register.py`: se
  ajustan las llamadas al nuevo nombre del método. La lógica no cambia.
- Vistas de pago y wizard: sin cambios, siguen publicando
  `check_sequence_next_number` en el contexto.

## Seguridad y multicompañía

`security/ir.model.access.csv` (nuevo):

| id | grupo | r | w | c | u |
|---|---|---|---|---|---|
| `access_account_checkbook_invoice` | `account.group_account_invoice` | 1 | 0 | 0 | 0 |
| `access_account_checkbook_manager` | `account.group_account_manager` | 1 | 1 | 1 | 1 |

`security/account_checkbook_security.xml`: record rule global
`['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`.

El avance del contador al postear sigue haciéndose con `sudo()`, así que un
usuario de Facturación puede postear aunque no tenga permiso de escritura
sobre la chequera.

## Migración `19.0.1.3.0`

`migrations/19.0.1.3.0/post-migrate.py`. Usa el ORM con `SUPERUSER_ID`,
porque en v19 `account.journal.name` es jsonb traducible.

1. Si la columna `account_journal.check_sequence_enabled` no existe, no
   hace nada (es una instalación nueva).
2. Lee por SQL `id, company_id, next_check_number, check_number_padding` de
   `account_journal` con `check_sequence_enabled IS TRUE`, `type = 'bank'`
   y `checkbook_id IS NULL`.
3. Para cada diario crea `account.checkbook` con:
   - `name` = `journal.name`
   - `next_number` = `next_check_number` (o `'00000001'` si está vacío)
   - `padding` = `check_number_padding` (o 8 si es inválido)
   - `company_id` = `journal.company_id`

   Después asigna `checkbook_id`.
4. Loguea la cantidad de chequeras creadas.

Es idempotente porque filtra `checkbook_id IS NULL`. Las columnas viejas
quedan en la base.

Para unificar dos diarios que ya venían numerando en paralelo, el
procedimiento es manual: en el diario B se elige la chequera del diario A,
se ajusta el próximo número si hace falta y se archiva la chequera que quedó
sin uso.

## Vistas y menú

- `views/account_checkbook_views.xml` (nuevo):
  - Lista: `name`, `next_number`, `padding`, `company_id` (con
    `groups="base.group_multi_company"`), `journal_ids` (`many2many_tags`).
  - Formulario: los mismos campos, `journal_ids` en solo lectura y la
    ribbon de archivado.
  - Búsqueda: `name`, filtro de archivadas.
  - Acción y menú: Contabilidad → Configuración → Bancos → **Chequeras**,
    visible solo para `account.group_account_manager`.
- `views/account_journal_views.xml`, grupo "Chequera / Numeración de
  Cheques Propios" (`invisible="type != 'bank'"`):
  - `checkbook_id` con `context="{'default_company_id': company_id}"`. La
    creación rápida crea la chequera con los defaults.
  - `next_check_number` y `check_number_padding` visibles solo si hay
    `checkbook_id`.
  - Si hay `checkbook_shared_journal_ids`, un `alert-info` que avisa: "Esta
    chequera también la usan:" seguido de los diarios. Si se cambia el
    próximo número, el cambio aplica a todos.

## Tests

`tests/test_check_sequence.py`:

- `setUp`: crea `self.checkbook` (`next_number='00001001'`) y la asigna a
  `self.bank_journal`.
- Los tests del contador (formato, incremento, salto manual, no retroceso,
  prefijo, cambio de serie, peek, más alto, lock, recálculo después del
  lock, padding) pasan a llamarse sobre `self.checkbook`. El `UPDATE` crudo
  del test de lock pasa a apuntar a `account_checkbook`.
- `check_sequence_enabled = False` se reemplaza por
  `self.bank_journal.checkbook_id = False`.
- Tests nuevos:
  - Dos diarios que comparten chequera: postear en A hace que B sugiera el
    número siguiente.
  - Una chequera sin compañía asignada a diarios de dos compañías: avanza
    correctamente desde ambas.
  - Una chequera de la compañía X asignada a un diario de la compañía Y
    lanza `ValidationError`.
  - Una chequera archivada no sugiere número y no avanza al postear.
  - Borrar una chequera en uso lanza un error (restrict).
  - Editar `next_check_number` desde el diario actualiza la chequera y se
    ve desde el otro diario.
  - Migración: con columnas viejas cargadas por SQL y `checkbook_id` nulo,
    `migrate(cr, '19.0.1.2.0')` crea la chequera con los valores
    correctos, y una segunda corrida no crea nada.

## Manifiesto y documentación

- `version`: `19.0.1.3.0`.
- `data`: `security/ir.model.access.csv`,
  `security/account_checkbook_security.xml`,
  `views/account_checkbook_views.xml`, más las vistas existentes.
- `summary` y `description`: pasan de "numeración por diario" a
  "chequeras, compartibles entre diarios y compañías".
- README: qué es una chequera, cómo compartirla, el procedimiento de
  unificación manual y el comportamiento de una chequera archivada.
- Sin i18n: los strings del módulo ya están en castellano.

## Fuera de alcance

- Varias chequeras activas por diario, o elegir la chequera en cada pago.
- Rangos de numeración (desde/hasta) y aviso de chequera agotada.
- Borrar las columnas viejas de `account_journal`.
- Unificación automática de chequeras en la migración.
