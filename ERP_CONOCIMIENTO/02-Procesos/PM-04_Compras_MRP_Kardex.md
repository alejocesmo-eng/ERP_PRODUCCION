---
id: PROC-MRP-001
titulo: Especificación del Motor MRP y Trazabilidad de Inventarios
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.4, 8.5.1
---
---
id: PROC-MRP-001
titulo: Especificación del Motor MRP y Planificación de Materiales
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.4, 8.5.1
modulo_equivalente_sap: SAP MM (Materials Management) / PP (Production Planning)
---

# [[PM-04_Compras_MRP_Kardex|Motor MRP y Trazabilidad de Abastecimiento]]

## 1. Algoritmo del Motor MRP (Explosión de Necesidades)
El motor MRP calcula los requerimientos netos consumiendo las demandas de las Órdenes de Producción confirmadas (`OPs`) y cruzándolas con las existencias físicas en Kárdex, retales y compras en tránsito:

$$\text{Requerimiento Neto (PR)} = \text{Demanda Bruta (BOM OPs)} - \left( \text{Stock Kárdex} + \text{Retales Reutilizables} + \text{POs en Tránsito} - \text{Stock Reservado} \right)$$

---

## 2. Reglas de Negocio Operativas
1. **Consolidación Automática por Material:** El MRP agrupa requerimientos de diferentes OPs que demanden la misma materia prima (ej. *AISI 4140 Ø 2.5"*), generando una **única Requisición de Compra (PR) consolidada** para optimizar costos de adquisición.
2. **Priorización de Retales (`MATERIAL_SOBRANTE`):** Antes de recomendar una compra externa, el MRP valida la disponibilidad en la tabla `retales_sobrantes` y sugiere su reserva si las dimensiones cubren el requerimiento técnico.
3. **Control de Liberación (`RN-OP-004`):** El almacén marca el material como `EN_ALMACEN` tras la recepción y validación de calidad (Certificado 3.1), habilitando la liberación de la OP a piso de planta.

---

## 3. Matriz de Mapeo Transaccional

| Entidad ERP | Campo Relacional | Módulo SAP Equivalente |
| :--- | :--- | :--- |
| `solicitudes_compra` | `codigo_op`, `codigo_plano` | SAP MM (Purchase Requisition - PR) |
| `lotes` | `numero_colada`, `certificado_3_1` | SAP MM (Batch Management) |
| `retales_sobrantes` | `codigo_retal`, `dimensiones` | SAP PP/MM (Scrap & Reusable Materials) |

---

## 4. Enlaces Relacionados
- [[Mapa de procesos]] - Flujo macro del ERP.
- [[Mapeo_Modulos_SGI_vs_SAP]] - Matriz de equivalencias SAP.
- [[RN-OP-004_Bloqueo_Liberacion_OP]] - Quality Gate de liberación a planta.