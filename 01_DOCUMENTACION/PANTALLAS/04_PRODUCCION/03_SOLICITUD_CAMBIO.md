# Pantalla: Control y Solicitud de Cambios Técnicos en OP

## 🎯 Objetivo
Gestionar solicitudes de cambio de material, ajuste de tolerancias o modificación de plano para una OP que ya fue liberada y se encuentra en piso de producción.

## 📝 Campos del Formulario
- `ID_Solicitud_Cambio`: Consecutivo (ej. `SC-2026-005`).
- `ID_OP`: Código de la OP afectada.
- `Solicitante`: Usuario de Producción o Diseño.
- `Tipo_Cambio`: `REVISION_PLANO`, `SUSTITUCION_MATERIAL`, `AJUSTE_DIMENSIONAL`.
- `Justificacion_Tecnica`: Campo obligatorio donde se detalla la causa del cambio.
- `Estatus_Aprobacion`: `PENDIENTE_APROBACION`, `APROBADO_JEFE_PRODUCCION`, `RECHAZADO`.

## 🔒 Regla de Control
- Si la solicitud es **APROBADA** por el Jefe de Producción, la OP se pausa temporalmente hasta que Diseño cargue la nueva versión del plano o la actualización de materiales.