# Pantalla: Solicitudes de Material Pendientes (Almacén)

##  Objetivo
Permitir al personal de almacén visualizar, priorizar y gestionar las Solicitudes de Material (SM) generadas por el departamento de Diseño para la preparación de órdenes de producción (OP).

##  Componentes y Filtros
- **Filtros Superiores**: Por Estado (`PENDIENTE`, `EN_PREPARACION`, `DESPACHADO`), por Prioridad (`ALTA`, `MEDIA`, `BAJA`) y por Código de OP.
- **Tabla / Lista de Solicitudes**:
  - `ID_Solicitud`: Código único de solicitud (ej. `SM-2026-001`).
  - `ID_OP`: Código de la Orden de Producción vinculada.
  - `Fecha_Solicitud`: Fecha y hora de emisión.
  - `Solicitante`: Usuario de Diseño.
  - `Estatus_Stock`: Indicador visual (`DISPONIBLE_TOTAL`, `RESERVA_PARCIAL`, `SIN_STOCK`).

##  Acciones Principales
- **Iniciar Preparación**: Cambia el estado a `EN_PREPARACION` y bloquea los ítems para reserva física.
- **Ver Detalle de Ítems**: Despliega la lista de materiales, dimensiones requeridas y sugerencias de retales aprovechables.