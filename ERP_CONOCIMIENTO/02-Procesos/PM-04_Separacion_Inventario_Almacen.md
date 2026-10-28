---
id: PROC-INV-002
titulo: Desacoplamiento Arquitectónico: Inventario General vs. Almacén Operativo
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.4 (Control de Procesos, Productos y Servicios Suministrados Externamente), 8.5.2 (Trazabilidad)
modulo_equivalente_sap: SAP MM-IM (Inventory Management) vs. SAP MM-WM/EWM (Warehouse Management)
---

# [[PM-04_Separacion_Inventario_Almacen|Desacoplamiento: Inventario General vs. Almacén Operativo]]

## 1. Responsabilidades

### Inventario General (MM-IM)
- Mantiene el maestro global de SKUs, categorías, unidades, stock mínimo y método de valoración.
- Registra el kárdex financiero inmutable, con costo promedio ponderado o FIFO.
- Mantiene lotes, colada, certificado 3.1 y el estado de inspección QM.
- Ejecuta el cálculo de requerimientos netos MRP usando stock liberado, retales y compras en tránsito.

### Almacén Operativo (MM-WM)
- Ejecuta la recepción física de requisiciones de compra que estén exactamente en `EN_COMPRA`.
- Registra despachos, consumos por OP, centros de costo, asignaciones y préstamos.
- Consulta el maestro de inventario bajo demanda; no mantiene un catálogo financiero propio.
- Conserva la operación de `Remanentes / Sobrantes` como flujo físico independiente.

## 2. Reglas de negocio e integración transaccional

1. **Maestro de materiales:** el SKU y su valoración se crean y administran en Inventario General. Almacén solo puede recibir un SKU ya registrado.
2. **Recepción (movimiento 101):** valida la requisición `EN_COMPRA`, registra factura/proveedor, crea un lote en `CUARENTENA`, actualiza saldo y valoración, y registra el kárdex en una única transacción de base de datos.
3. **Control QM:** Calidad puede cambiar el lote entre `CUARENTENA`, `LIBERADO` y `RECHAZADO`; cada cambio requiere motivo y genera una auditoría inmutable. Hasta que se reciban las cantidades requeridas y todos los lotes de la PR estén `LIBERADO`, la PR/BOM conserva el bloqueo de abastecimiento; solo entonces cambia a `EN_ALMACEN`. Solo un lote `LIBERADO` es elegible para despacho.
4. **Consumo de OP (movimiento 261):** exige una OP existente y despacha mediante FIFO físico. La valoración financiera usa el método definido en el SKU. La transacción también registra el costo de material de la OP.
5. **Otras salidas (movimiento 201):** no pueden consumir stock reservado ni material en cuarentena o rechazado.
6. **Kárdex auditable:** las entradas/salidas no se editan ni borran; correcciones futuras deben registrarse como movimientos de ajuste compensatorios.
7. **MRP:** el stock de lotes en cuarentena o rechazados no reduce la necesidad neta ni autoriza la liberación de producción. El MRP conserva la trazabilidad independiente N:M entre pedidos comerciales, planos y OP.

## 3. Trazabilidad técnica

| Proceso | Tabla / registro | Servicio | Pantalla |
| --- | --- | --- | --- |
| Catálogo maestro | `articulos_inventario`, `categorias_inventario` | `/api/v1/inventario/articulos`, `/api/v1/inventario/categorias` | `InventarioGeneralView.jsx` |
| Recepción / movimiento 101 | `lotes_material`, `movimientos_inventario`, `solicitudes_compra` | `/api/v1/almacen/recepcion-compra` | `AlmacenInventarioView.jsx` |
| Inspección de lote | `auditoria_calidad_lotes` | `/api/v1/inventario/lotes/{id}/calidad` | `InventarioGeneralView.jsx` |
| Despacho / movimientos 261 y 201 | `lotes_material`, `movimientos_inventario`, `consumos_material_op` | `/api/v1/inventario/articulos?disponible=true`, `/api/v1/almacen/salidas` | `AlmacenInventarioView.jsx` |
| Kárdex / valoración | `movimientos_inventario` | `/api/v1/inventario/kardex` | `InventarioGeneralView.jsx` |
| Requerimientos netos | `requisiciones_mrp`, `solicitudes_compra` | `/api/v1/solicitudes-compra/mrp/ejecutar` | `InventarioGeneralView.jsx` |

El cambio de esquema requerido está definido en `05_BASE_DATOS/05_MIGRACION_INVENTARIO_GENERAL.sql`. La migración clasifica como cuarentena el saldo legado que carezca de lotes trazables; la liberación requiere inspección por Calidad.

## 4. Enlaces relacionados

- [[Mapeo_Modulos_SGI_vs_SAP]] - Equivalencias con SAP MM/QM.
- [[PM-04_Compras_MRP_Kardex]] - Motor de requerimientos netos.
- [[RN-OP-004_Bloqueo_Liberacion_OP]] - Quality Gate de liberación de OP.
