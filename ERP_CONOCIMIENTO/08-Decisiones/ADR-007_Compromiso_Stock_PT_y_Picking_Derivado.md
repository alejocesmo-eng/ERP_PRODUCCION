---
id: ADR-007
titulo: Compromiso de stock de producto terminado al confirmar pedido, con saldo derivado de las órdenes de picking
estado: propuesto
fecha: 2026-10-30
autor: arquitecto-datos (Oficina de Agentes IA)
ot: OT-2026-008
iso_9001_2026: Cláusulas 8.2.3, 8.5.1, 8.5.2, 7.1.3
relacionados: ["[[OT-2026-008]]", "[[ADR-001_Jerarquia_Relacional_NM]]", "[[RN-LOG-002_Compromiso_Stock_Apartados]]", "[[Modelo_ERD_PostgreSQL]]", "[[CONSTITUCION_OFICINA_IA]]"]
---

# ADR-007: Compromiso de stock PT al confirmar el pedido; saldo derivado del picking

## 1. Contexto
- Ventas necesita cargar producto terminado (PT) existente en cotizaciones y pedidos sin reservar al cotizar (instrucción de Dirección, OT-2026-008, G1).
- No existen hoy `ordenes_picking` ni reservas de ventas. `articulos_inventario.stock_reservado` lo sobrescribe `almacen.py:446-470` al reservar para BOM/OP, por lo que no puede alojar compromisos de ventas.
- El saldo vigente (`inventario.py:109-137`) es `min(LIBERADO, stock_actual) - reservado`. Falta restar lo comprometido a pedidos y lo que está en picking.
- `RN-LOG-002` (aprobada) prevé reservas temporales de 48 h al cotizar de forma verbal; contradice la instrucción de Dirección para la cotización formal.
- La relación N:M `proyectos` ↔ `planos` (ADR-001) debe mantenerse intacta.

## 2. Decisión
1. **El compromiso ocurre solo al confirmar el pedido.** Cotizar y guardar un pedido sin confirmar no modifican el saldo. Se valida la disponibilidad al agregar, guardar y confirmar, sobre la suma de líneas por SKU.
2. **Comprometido y En Picking se derivan, no se almacenan.** Se calculan desde `ordenes_picking_detalle` según el estado de `ordenes_picking` (`PENDIENTE` = comprometido; `EN_PICKING` = en picking). Disponible = vendible liberado - reservado OP - comprometido - en picking. No se agregan columnas contador a `articulos_inventario`.
3. **Concurrencia:** la confirmación bloquea la fila del pedido y las filas de `articulos_inventario` implicadas con `SELECT ... FOR UPDATE`, en orden fijo por `id_articulo`, recalcula el saldo y crea el picking en una sola transacción. Todo futuro camino que comprometa stock de venta debe tomar el mismo bloqueo.
4. **Idempotencia:** un pedido tiene como máximo un picking (`UNIQUE(id_proyecto)`); confirmar de nuevo un pedido confirmado devuelve el estado sin crear nada.
5. **Origen de la línea:** `pedido_detalles` y `posiciones_cotizacion` reciben `origen` (`PLANO` | `STOCK_PT`) e `id_articulo`. Las líneas `STOCK_PT` no tienen `ot_detalles` ni planos; la N:M `proyectos` ↔ `planos` y RN-OP-004 no cambian.
6. **Confirmar un pedido con stock genera picking, no orden de producción.** Un pedido mixto genera picking solo para las líneas de stock.
7. **Se excluyen** `reservas_stock_temporal` y la reserva de 48 h (RN-LOG-002) para la cotización formal. RN-LOG-002 debe actualizarse en F6 para reflejarlo, o Dirección revierte esta decisión.

## 3. Consecuencias
- Positivas: una sola fuente para el saldo comprometido; no se pierden datos por sobrescritura; migración aditiva y reversible; no se toca la N:M.
- Negativas: el saldo exige una consulta agregada; mientras no exista el despacho (otra OT) el stock comprometido no se libera ni se descuenta; las vistas de inventario existentes no restan los compromisos de ventas hasta unificar el cálculo.
- Neutras: cantidades enteras en esta OT; decimales requieren una migración de tipos aparte.

## 4. Alternativas descartadas
- Columnas `stock_comprometido` y `stock_en_picking` en `articulos_inventario`: dato duplicado, deben mantenerse en cada transición.
- Reutilizar `stock_reservado`: se sobrescribe desde `almacen.py`.
- Reservar al cotizar con vencimiento de 48 h: contradice la instrucción de Dirección.
- Reutilizar `vinculo_plano_catalogo` como origen: es referencia a plano, semántica distinta.

## 5. Estado
`propuesto`. Pasa a `aprobado` solo con la aprobación de Dirección en G2 de la OT-2026-008.
