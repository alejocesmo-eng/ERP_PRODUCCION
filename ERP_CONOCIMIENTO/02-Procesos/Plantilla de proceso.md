---
tipo: proceso
estado: borrador
responsable: por-confirmar
modulo: por-confirmar
version: 0.1
---

# ---
tipo: proceso
codigo: PROC-PROD-001
nombre: Gestión y Ejecución de Órdenes de Producción (Mecanizado CNC)
version: 1.0
estado: en_revision
fase_target: F1-F3
responsable_proceso: Jefe de Operaciones / Líder de Mecanizado
sistema_origen: AppSheet / Manual
sistema_destino: ERP FastAPI + PostgreSQL
---

# Proceso: Gestión y Ejecución de Órdenes de Producción (Mecanizado CNC)

## 1. Propósito y Alcance
- **Propósito**: Normar y estandarizar el flujo de información, asignación de recursos, cronometraje en puesto de trabajo, inspección metrológica y liberación final de piezas mecanizadas mediante CNC.
- **Alcance**: Inicia desde la recepción del Pedido Comercial verificado y la apertura de la Orden de Producción (serie `400XXXX`) en el área de Diseño, hasta el cierre de la OP por el Jefe de Operaciones y la transferencia del lote a Logística para su despacho.

## 2. Definiciones y Siglas
- **OP**: Orden de Producción.
- **CNC**: Control Numérico Computarizado (Tornos y Centros de Mecanizado).
- **BOM**: Lista de Materiales (*Bill of Materials*).
- **Setup**: Tiempo de alistamiento y montaje de herramientas/piezas en máquina.
- **NC**: No Conformidad.
- **Tratamiento Térmico (TT)**: Proceso térmico externo contratado para modificación de propiedades mecánicas.

## 3. Entradas, Salidas y Recursos

### Entradas
- Pedido Comercial confirmado con especificaciones técnicas del cliente.
- Muestra física, medidas tomadas en sitio o planos entregados por el cliente (según el caso).

### Salidas
- Piezas mecanizadas y verificadas dimensionalmente.
- Reporte metrológico de inspección de Calidad.
- Informe de Tratamiento Térmico con registro fotográfico (si aplica).
- Registros de tiempos de Setup y Mecanizado asociados a la OP y al operario.
- OP en estado `Cerrada`.

### Recursos e Instrumentos
- **Maquinaria**: Tornos CNC, Centros de Mecanizado CNC, máquinas convencionales de apoyo.
- **Instrumentos Metrológicos**: Micrómetros (interiores/exteriores), Calibradores pie de rey, Patrones de calibración/bloques patrón.
- **Herramental**: Insertos, plaquitas, portaherramientas, brocas, fresas (gestión de stock migrado).

## 4. Diagrama del Proceso

```mermaid
workflow
    title Flujo de Ejecución OP Mecanizado CNC (Serie 400XXXX)
    
    state "Diseño: Creación OP (400XXXX)" as D_Create
    state "Estado: Planificada" as ST_Plan
    state "Estado: Programada" as ST_Prog
    state "Diseño: Planos + BOM/Solicitud Compras" as D_Work
    state "Estado: Liberada" as ST_Lib
    state "Producción: Asignación a Operario/Máquina" as P_Assign
    state "Puesto CNC: Cronómetro Setup" as P_Setup
    state "Puesto CNC: Cronómetro Mecanizado" as P_Prod
    state "Calidad: Revisa Metrología (Micrómetros/Pie de Rey)" as Q_Insp
    state "Calidad: Informe TT + Envío a Proveedor" as Q_TT
    state "Producción: Acabado Post-Tratamiento" as P_Finish
    state "Gestión NC: Solicitud Nuevo Material + Reproceso" as Q_NC
    state "Jefe Operaciones: Cierre OP" as OP_Close

    [*] --> D_Create
    D_Create --> ST_Plan
    ST_Plan -->|Completar medidas/planos/muestra| ST_Prog
    ST_Prog --> D_Work
    D_Work --> ST_Lib
    ST_Lib --> P_Assign
    P_Assign --> P_Setup
    P_Setup --> P_Prod
    P_Prod --> Q_Insp
    
    Q_Insp -->|Aprobado con TT| Q_TT
    Q_TT --> P_Finish
    P_Finish --> Q_Insp
    
    Q_Insp -->|No Conformidad / Falla Dimensional| Q_NC
    Q_NC --> ST_Plan
    
    Q_Insp -->|Aprobado Definitivo| OP_Close
    OP_Close --> [*]