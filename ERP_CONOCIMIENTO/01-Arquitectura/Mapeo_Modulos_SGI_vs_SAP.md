---
id: MAP-SAP-001
titulo: Mapeo de Capacidades SGI-ERP vs SAP S/4HANA
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.1, 8.3, 8.4, 8.5
---

# [[Mapeo_Modulos_SGI_vs_SAP|Equivalencia Funcional SGI-ERP vs SAP]]

## 1. Visión de Integración Transversal
Al igual que SAP, el SGI-ERP asegura que ningún evento operativo (ej. consumo de un bloque de acero en máquina CNC) ocurra de forma aislada; todo movimiento genera un registro transaccional que impacta en tiempo real al Kárdex de Almacén, el costo real de la OP y el avance del Pedido Comercial.

---

## 2. Matriz de Mapeo de Módulos y Reglas

| Módulo SGI-ERP | Módulo SAP Equivalente | Funcionalidad Clave a Nivel SAP | Regla o Componente en SGI-ERP |
| :--- | :--- | :--- | :--- |
| **PM-01 Ventas** | **SAP SD (Sales & Distribution)** | Flujo: Cotización → Pedido Inmutable → Control ATP (Available to Promise). | Inmutabilidad de `proyectos` tras confirmación (`RN-COM-001`). |
| **PM-02 Ingeniería** | **SAP PLM / Variant Config** | BOM multinivel, Hojas de Ruta (Routings) y Control de Cambios de Ingeniería (ECM). | Asignación $N:M$ en `ot_detalles` y versión de plano PDF. |
| **PM-03 MES Planta** | **SAP PP / DMC (Digital Mfg)** | Programación de capacidad finita, Notificación de tiempos y Backflushing de insumos. | Cronómetro de alistamiento/mecanizado en Tablet MES y sublotes. |
| **PM-04 Compras** | **SAP MM (Materials Mgmt)** | Motor MRP automático, Valoración Kárdex (FIFO/Promedio) y Calificación de Proveedores. | Requisiciones de Compra (PR) ligadas a BOM (`solicitudes_compra`). |
| **PM-05 Calidad** | **SAP QM (Quality Mgmt)** | Bloqueo por Cuarentena (Quality Stock), Planes de Inspección y Certificado 3.1. | Gate `RN-OP-004` (Plano + Material) y Notificación de Elegibilidad. |
| **Costos / Finanzas** | **SAP CO (Controlling)** | Liquidación de OP: Costo Real ($\text{Materia Prima} + \text{Horas Hombre/Máquina} + \text{Terceros}$). | Acumulación de tiempos MES y consumos de inventario por `codigo_op`. |

---

## 3. Cadena de Trazabilidad Transversal ($N:M$)

$$\text{Cliente (SD)} \longrightarrow \text{Pedido Comercial} \longrightarrow \text{BOM / Routing (PLM)} \longleftrightarrow \text{Requisición/Stock (MM)} \longleftrightarrow \text{OP CNC (PP/MES)} \longrightarrow \text{Certificado 3.1 (QM)}$$

---

## 4. Enlaces Relacionados en el Vault
- [[Mapa de procesos]] - Proceso macro de la empresa.
- [[ADR-001_Jerarquia_Relacional_NM]] - Separación Comercial vs Planta.
- [[RN-OP-004_Bloqueo_Liberacion_OP]] - Gate de liberación de órdenes.