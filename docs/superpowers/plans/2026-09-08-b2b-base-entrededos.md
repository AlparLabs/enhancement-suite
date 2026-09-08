# Plan de Implementación — Intranet Base B2B EntreDos con Bloqueo Financiero

**Fecha:** 2026-09-08  
**Cliente:** EntreDos  
**Plataforma:** Odoo 19 Enterprise sobre Odoo.sh  
**Rama objetivo:** `19.0`  
**Especificación de referencia:** [docs/superpowers/specs/2026-09-08-b2b-base-entrededos-design.md](file:///c:/Users/Santiago/Desktop/Desarrollo/enhancement-suite/docs/superpowers/specs/2026-09-08-b2b-base-entrededos-design.md)

---

## 1. Objetivo y Descomposición

Construir la **Base B2B** para EntreDos sobre Odoo 19 con dos módulos desacoplados:
1. `website_sale_b2b_credit_block`: Bloqueo financiero automático por deuda facturada, días de gracia por website, mensaje elegante de excedente y resolución de acceso por canal.
2. `website_sale_product_channel_ux`: Vistas optimizadas y acción en lote para catalogación por canal.

---

## 2. Tareas de Construcción

### Fase 1: Módulo `website_sale_b2b_credit_block`

- [ ] **Tarea 1.1: Estructura base y manifest**
  - Crear `website_sale_b2b_credit_block/__init__.py` y `__manifest__.py`.
  - Configurar dependencias: `website_sale`, `account`, `sale`.
- [ ] **Tarea 1.2: Modelo `website` y días de gracia**
  - Campos `b2b_credit_block_active` y `b2b_grace_period_days`.
  - Override de `has_ecommerce_access()` con bypass de internal users y chequeo de `b2b_website_ids`.
- [ ] **Tarea 1.3: Modelo `res.partner` y canales web**
  - Campo `b2b_website_ids` (M2M con `website`).
  - Campo `b2b_grace_period_override`.
  - Override de `get_base_url()` para enlaces de portal wizard.
- [ ] **Tarea 1.4: Lógica de evaluación financiera en `sale.order`**
  - Método `_get_b2b_financial_status(website)`.
  - Facturas vencidas impagas con corte por días de gracia.
  - Exposición de crédito: `partner.credit + order.amount_total` vs `partner.credit_limit`.
  - Cálculo de `excess_amount`.
  - Override de `action_confirm()` con estado `waiting_approval`.
- [ ] **Tarea 1.5: Controladores web y prevención de bucle**
  - Override de rutas de tienda `/shop`, `/shop/cart`, `/shop/checkout`.
  - Si no tiene acceso al canal, redirigir a `/my` (evitar bucle `/web/login`).
  - Inyectar el estado financiero en el contexto del checkout y bloquear confirmación a Cuenta Corriente si está en falta.
- [ ] **Tarea 1.6: Vistas y Templates QWeb**
  - Formulario de sitio web y configuración de días de gracia.
  - Solapa de ventas en `res.partner` con canales autorizados.
  - Template QWeb heredado en el carrito/checkout para mostrar el banner elegante con desglose de deuda y excedente.
- [ ] **Tarea 1.7: Pruebas automatizadas unitarias e HttpCase**
  - Tests de días de gracia y fechas de vencimiento.
  - Tests de límite sobre deuda facturada (excluyendo órdenes no facturadas).
  - Tests de acceso a tienda y navegación cruzada.

---

### Fase 2: Módulo `website_sale_product_channel_ux`

- [ ] **Tarea 2.1: Estructura base y manifest**
  - Crear `website_sale_product_channel_ux/__init__.py` y `__manifest__.py`.
- [ ] **Tarea 2.2: Vistas de `product.template`**
  - Campo `website_id` destacado en el formulario con placeholder explicativo.
  - Columna `website_id` en vista lista (`optional="show"`).
  - Filtros por canal y agrupador en vista de búsqueda.
- [ ] **Tarea 2.3: Wizard de asignación masiva de canal**
  - Modelo transitorio `product.channel.assign.wizard`.
  - Acción de servidor registrada en el menú "Acción" de la lista de productos.
- [ ] **Tarea 2.4: Pruebas automatizadas**
  - Test de ejecución masiva del wizard.

---

## 3. Criterios de Aceptación del Plan

1. El franquiciado logueado en Franquicias opera en su catálogo y precios sin saltos ni redirecciones erróneas.
2. Si un franquiciado tiene mora fuera de días de gracia, el checkout le muestra la deuda y bloquea Cuenta Corriente.
3. Si la nueva compra excede el límite disponible, el banner calcula el excedente exacto sin mostrar el límite interno de \$1M.
4. Si la compra está dentro del límite y sin mora, se confirma directamente en Cuenta Corriente.
5. El equipo de EntreDos puede clasificar masivamente productos por canal desde la lista del backoffice.
