---
id: PM-06
proceso: Logística, Almacén de PT y Distribución
responsable: Coordinador de Logística / Responsable de Almacén
iso_9001_2026: Cláusula 8.5.4 (Preservación de las salidas) / 8.6 (Liberación de productos)
estado: APROBADO
---

# [[PM-06_Logistica_Custodia_Despacho]]

## 1. Alcance y Propósito
Este proceso gobierna la custodia física del Producto Terminado (PT), la ejecución operativa de picking y despacho vinculados a Ventas [[PM-01_Ventas_y_CRM]], la recepción/devolución de máquinas de clientes para mantenimiento técnico [[MantenimientoPlantaView]], y la reposición proactiva de stock hacia Producción [[PM-03_Produccion_MES_Capacity]].

---

## 2. Flujos Clave de Operación

### Flujo A: Ventas contra Stock y Despacho (Picking $\rightarrow$ Packing $\rightarrow$ Despacho)
1. **Emisión de Orden de Picking:** Ventas emite la orden tras confirmación comercial. Las unidades comprometidas se descuentan automáticamente del stock vendible público.
2. **Ejecución de Picking:** Operario de logística recolecta los ítems en bodega mediante lista de picking digital.
3. **Punto de Rebaje de Kárdex:** La disminución definitiva del kárdex físico y contable se genera al cambiar la orden a estado `DESPACHADO` (asociando transportador, remisión o guía).

### Flujo B: Custodia y Mantenimiento Técnico de Equipos Externos
1. **Recepción:** Ingreso formal con número de serie individual, registro fotográfico de estado inicial, inventario de accesorios y motivo de ingreso.
2. **Ubicación:** Asignación a zona de custodia `BOD_TALLER_CUSTODIA` (sin impacto en kárdex comercializable).
3. **Entrega / Retorno:** Validación de orden técnica cerrada y firma de entrega a satisfacción.

### Flujo C: Reposición de Stock Asistida por Humano (Mínimos y Máximos)
1. **Monitoreo Proyectado:** El sistema calcula continuamente:
   $$\text{Stock Proyectado} = \text{Stock Físico} + \text{OPs en curso} - \text{Comprometido (Preventa)} - \text{En Picking}$$
2. **Semáforo:** Alerta amarilla (Punto de Reorden) y roja (Stock de Seguridad).
3. **Intervención Humana:** El sistema NO emite la OP automáticamente; el responsable de Logística analiza la necesidad, valida el lote mínimo (MOQ) y confirma la creación de la OP de Stock (origen `REPOSICION_STOCK`, series $4xxxxxx$ o $1xxxxxx$).

---

## 3. Enlaces Relacionados
- [[Modelo_ERD_PostgreSQL]]
- [[RN-LOG-001_Flujo_Picking_Despacho]]
- [[RN-LOG-002_Compromiso_Stock_Apartados]]
- [[Matriz_de_trazabilidad]]