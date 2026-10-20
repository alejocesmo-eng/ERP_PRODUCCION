---
tipo: mapa-procesos
estado: borrador
---
---
tipo: mapa-procesos
estado: en_revision
fase_target: F1-F3
sistema_origen: AppSheet / Manual
sistema_destino: ERP FastAPI + PostgreSQL
---

# Mapa general de procesos

> Documento de arquitectura funcional y mapa de flujo para el ERP de manufactura (Mecanizado CNC, Metalistería y Servicios).

## Procesos estratégicos
- **Gestión de Capacidad y Programación Operativa**: Planeación de balanceo de cargas de trabajo en taller CNC y metalistería.
- **Gestión de Calidad ISO / Estándares Alimentarios**: Control de metrología, trazabilidad de piezas, tratamientos térmicos y gestión de no conformidades.

## Procesos operativos

```mermaid
graph TD
    A[Ventas: Pedido Comercial] --> B{Confirmación Cliente}
    B -->|Confirmado| C[Diseño: Apertura OP por Ítem]
    C --> D[Estado: Planificada]
    D -->|Motivos: Faltan medidas / planos / muestra| D
    D -->|Información Completa| E[Estado: Programada]
    E --> F[Diseño: Elaboración de Planos + Solicitud BOM/Compras]
    F --> G[Estado: Liberada]
    G --> H[Producción: Asignación Líder a Operario/Estación]
    H --> I[Ejecución CNC / Metalistería / Servicios]
    I --> J[Calidad: Inspección Metrológica]
    J -->|Requiere Tratamiento Térmico| K[Calidad: Informe + Envío a Proveedor]
    K --> L[Retorno a Planta: Acabado/Mecanizado Final]
    L --> J
    J -->|Aprobado Final| M[Informe Calidad + Cierre OP por Jefe Operaciones]
    M --> N[Logística: Despacho a Cliente]