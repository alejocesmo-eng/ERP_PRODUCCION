
# Pantalla: Orden de Producción en Proceso (Planta)

## Objetivo
Visualizar el detalle operativo, parámetros de fabricación, componentes de la lista de materiales (BOM), planos vigentes y herramental asignado a una Orden de Producción activa en máquina.

##  Estructura y Secciones
- **Encabezado de la OP**:
  - `ID_OP`: Código único de la Orden (ej. `OP-2026-0042`).
  - `Cliente` | `Proyecto` | `Fecha_Compromiso`.
  - `Estado_OP`: `LIBERADA`, `EN_FABRICACION`, `PAUSADA`, `PENDIENTE_CALIDAD`.
  - `Máquina_Asignada`: Identificador de máquina (ej. `0357`).
- **Sección Técnica (Diseño)**:
  - Enlace al plano técnico vigente (solo lectura de la última versión/revisión aprobada).
  - Especificación de materia prima asignada o retal reservado (`RET-XXXXXX`).
- **Sección de Herramental y Consumibles**:
  - Lista de portaherramientas (ej. `0357-01`) e insertos requeridos con stock descontado por Almacén.

##  Acciones Principales
- **Iniciar/Pausar Turno**: Registro de tiempo de máquina activa.
- **Solicitar Cambio Técnico**: Abrir formulario de modificación en caso de imprevistos en planta.
- **Registrar Avance**: Acceso directo al formulario de reporte de piezas.