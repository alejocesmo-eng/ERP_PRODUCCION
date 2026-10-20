# Pantalla: Control, Cubicación y Etiquetado de Retales (Almacén)

## Objetivo
Identificar, cubicación (dimensionamiento) y registrar retales metálicos u otros sobrantes de producción aprovechables para reutilización en futuros proyectos.

##  Estructura de Captura
- `ID_Retal`: Código único generado por sistema (ej. `RET-001234`).
- `Material_Padre`: Tipo de aleación / norma (ej. `AISI 4140`, `Inox 304`).
- `Dimensiones`:
  - `Largo` (mm) | `Ancho / Diámetro` (mm) | `Espesor` (mm).
- `Ubicación_Física`: Zona de retales / Rack asignado.
- `Estado_Retal`: `DISPONIBLE`, `RESERVADO_DISEÑO`, `CONSUMIDO`.
- `OP_Origen`: Orden de producción de la cual surgió el retal.

##  Funcionalidades
- **Generar Etiqueta QR**: Opción para imprimir etiqueta con el código `RET-XXXXXX` y dimensiones para pegado físico en el retal.