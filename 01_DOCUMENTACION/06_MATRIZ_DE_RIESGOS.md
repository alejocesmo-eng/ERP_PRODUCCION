# 06 — MATRIZ DE RIESGOS Y CONTROLES DEL FLUJO CRÍTICO (ISO 9001:2026)

**Versión:** 1.0  
**Estado:** Documento base de diseño  
**Propósito:** Definir los riesgos operacionales del flujo misional y especificar las reglas de negocio que el software forzará automáticamente para mitigarlos.

---

## 1. FLUJO MISIONAL EVALUADO

$$\text{VENTAS} \longrightarrow \text{DISEÑO} \longrightarrow \text{CALIDAD / OP} \longrightarrow \text{ALMACÉN} \longrightarrow \text{PRODUCCIÓN} \longrightarrow \text{METROLOGÍA} \longrightarrow \text{ENTREGA}$$

---

## 2. MATRIZ OPERATIVA DE RIESGOS Y CONTROLES EN SOFTWARE

| Código | Proceso | Riesgo Identificado | Impacto en el SGI | Control de Calidad | Regla del Software / Validación |
|---|---|---|---|---|---|
| **R-PM01-01** | Ventas / Clientes | Requisitos o especificaciones del cliente incompletos o ambiguos. | Retrasos en diseño, piezas no conformes o reclamos. | Checklist de entrada de proyecto obligatoria. | **RN-VT-001:** No se permite pasar el proyecto a "CONFIRMADO" sin completar especificaciones obligatorias y fecha comprometida. |
| **R-PM02-01** | Diseño e Ingeniería | Uso de una revisión obsoleta de un plano en producción. | Fabricación no conforme, reprocesos y desperdicio de materia prima. | Control de revisiones e inmutabilidad de versiones. | **RN-DS-001:** La aprobación de una nueva revisión (REV-02) deshabilita y marca automáticamente la versión previa (REV-01) como OBSOLETA. |
| **R-PM03-01** | Calidad / OP | Emisión de la Orden de Producción sin revisión técnica independiente. | Pérdida de control de calidad y falta de rigor técnico en planta. | Exclusividad de validación por el rol de Calidad. | **RN-OP-001:** Solamente usuarios con rol Calidad pueden cambiar el estado de la OP de "BORRADOR" a "APROBADA". |
| **R-PM03-02** | Calidad / OP | Liberación de OP a piso de producción sin disponibilidad total de insumos. | Paradas de planta y desorganización en el flujo de trabajo. | Verificación de inventario reservado contra BOM de Ingeniería. | **RN-OP-004:** Bloqueo estricto del cambio a "LIBERADA_PRODUCCION" si la reserva de materia prima en Almacén es < 100%. |
| **R-PM04-01** | Almacén / Materiales | Despacho de material equivocado o sin trazabilidad de lote/colada. | Contaminación de lote y ensamble fuera de norma. | Trazabilidad obligatoria por número de lote. | **RN-AL-001:** El sistema exige asociar un número de lote activo y con inspección aprobada en cada movimiento de material. |
| **R-PM05-01** | Producción | Avance de fabricación sin planos autorizados vigentes. | Piezas fabricadas fuera de norma o fuera de tolerancia. | Visualización de plano activo en terminal de planta. | **RN-PR-001:** La terminal de planta solo despliega el plano técnico en estado APROBADO correspondiente a la versión vigente. |
| **R-PM06-01** | Metrología | Inspección de producto final con instrumentos de medición vencidos. | Lecturas dimensionales erróneas y falsa conformidad. | Hoja de vida y vigencia de calibración de equipos. | **RN-MT-001:** El sistema inhabilita la selección de instrumentos cuya fecha de calibración esté vencida en la ficha de metrología. |
| **R-PC03-01** | No Conformidades | Cierre administrativo de No Conformidades sin análisis de causa raíz. | Reincidencia de fallas y falta de mejora continua. | Flujo de cierre en dos etapas (Acción y Eficacia). | **RN-NC-001:** No se puede pasar una NC a estado "CERRADA" sin adjuntar el análisis de causa (5 Porqués) y la firma de Calidad. |

---

## 3. MECANISMO DE EJECUCIÓN TÉCNICA

1. **Backend (FastAPI):** Cada regla (`RN-*`) se implementa mediante validaciones en los endpoints y servicios de dominio (`app/api/v1/`).
2. **Base de Datos (PostgreSQL):** Restricciones de integridad mediante `CHECK constraints`, `FOREIGN KEY` y disparadores (`triggers`).
3. **Frontend (React):** La interfaz bloquea dinámicamente botones y acciones según la matriz **ROL + PROCESO + ESTADO**.