---
tipo: calidad
codigo: PRO-CAL-001
nombre: Inspección Metrológica, Tratamiento Térmico y Gestión de No Conformidades
fase: F1-F4
modulo: Calidad de Producto
prioridad: ALTA
estado: en_revision
autor: Analista Funcional / Arquitecto de Software
sistema_origen: AppSheet / Registro Manual
sistema_destino: ERP FastAPI + PostgreSQL
---

# PRO-CAL-001: Inspección Metrológica, Tratamiento Térmico y Gestión de No Conformidades

## 1. Propósito y Alcance
- **Propósito**: Normar el procedimiento de verificación metrológica dimensional de piezas mecanizadas, el control de envíos a Tratamiento Térmico (TT) externo y la gestión de No Conformidades (NC) con re-solicitud de materia prima en el ERP.
- **Alcance**: Aplica a todas las Órdenes de Producción (series `100XXXX`, `300XXXX` y `400XXXX`) al finalizar una etapa de mecanizado/estación en planta, hasta la emisión del informe de liberación final para despacho o la generación de una NC por Scrap.

---

## 2. Diagrama de Flujo del Módulo de Calidad

```mermaid
graph TD
    A[Producción: OP Terminada en Estación] --> B[Ingreso a Cola de Calidad]
    B --> C[Inspección Metrológica: Micrómetro / Pie de Rey / Patrón]
    C --> D{¿Cumple Tolerancias de Plano?}
    
    D -->|SÍ - Requiere Tratamiento Térmico| E[Generación Informe TT + Registro Fotográfico]
    E --> F[Envío Automático Email a Proveedor]
    F --> G[Reingreso a Planta: Acabado Final]
    G --> C

    D -->|SÍ - Pieza Final Aprobada| H[Informe de Aprobación Metrológica]
    H --> I[Jefe de Operaciones: Cierre de OP]
    I --> J[Habilitación para Despacho / Logística]

    D -->|NO - Fuera de Tolerancia / Defectuoso| K[Registro de No Conformidad - NC]
    K --> L[Solicitud Automática Re-despacho Materia Prima]
    L --> M[Re-inicio de Ciclo Mecanizado / Reproceso]