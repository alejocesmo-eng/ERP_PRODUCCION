---
id_regla: RN-VEN-002
nombre: Mapeo de stock de producto terminado en cotización y pedido
proceso_asociado: PM-01 Ventas / PM-06 Logística
estado: borrador
origen: "[[OT-2026-008]]"
advertencia: "El identificador RN-VEN-002 ya existe en 01_DOCUMENTACION/09_REGLAS_DE_NEGOCIO_SGI.md:18 (Control de Cambios). Dirección debe decidir el ID definitivo."
---

# RN-VEN-002 (borrador): Mapeo de stock PT en cotización y pedido

> Nota en estado `borrador`: solo orienta, no autoriza (Constitución GOB-IA-001 §2, nivel 7). Aprobación pendiente en G1 de [[OT-2026-008]].

## 1. Regla propuesta por Dirección (sin cambios de fondo)
1. El catálogo de stock para ventas muestra solo ítems de categoría `PRODUCTO_TERMINADO`.
2. Disponible para venta = Stock Físico − Comprometido − En Picking (fórmula de [[RN-LOG-002_Compromiso_Stock_Apartados]]).
3. Cotización: precarga SKU, descripción y precio; **no reserva** ni modifica saldo (la cotización no es vinculante).
4. Pedido: se pueden cargar líneas desde stock solo si `confirmado = False`; con `confirmado = True` se rechaza en interfaz y API (HTTP 400).
5. Cada posición desde stock se registra en el detalle del pedido (`pedido_detalles`).
6. Al confirmar el pedido con stock PT se genera una orden de picking (logística), no una orden de producción.

## 2. Estado de verificación (ver OT-2026-008 sección 1)
- Documentado: fórmula de disponibilidad, picking y `pedido_detalles` ([[Modelo_ERD_PostgreSQL]], [[RN-LOG-002_Compromiso_Stock_Apartados]], [[PM-06_Logistica_Custodia_Despacho]]).
- Implementado: bloqueo de edición de pedido confirmado (`proyectos.py:519-523`).
- No implementado: catálogo PT para ventas, `ordenes_picking`, stock comprometido/en picking, reservas.
- Todo "no verificado en ejecución".

## 3. Puntos abiertos (resolver en G1; no se asumen)
- ID definitivo de la regla (colisión).
- Cuándo se revalida la disponibilidad (al agregar la línea, al guardar, al confirmar).
- Si un pedido sin confirmar reserva stock.
- Qué crea el picking y quién confirma.

## 4. Relacionados
[[RN-LOG-002_Compromiso_Stock_Apartados]] · [[PM-06_Logistica_Custodia_Despacho]] · [[Modelo_ERD_PostgreSQL]] · RN-VT-001 · RN-OP-004
