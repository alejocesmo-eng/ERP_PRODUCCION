# APROBACIÓN DE ORDEN DE PRODUCCIÓN

## 1. Objetivo

Esta pantalla permite a Calidad registrar la aprobación o rechazo de una Orden de Producción después de realizar la inspección correspondiente.

La aprobación de Calidad constituye un requisito obligatorio para el cierre de la OP.

---

## 2. Acceso

Permisos:

- CALIDAD_VER
- CALIDAD_APROBAR
- CALIDAD_RECHAZAR

---

## 3. Requisitos para aprobar

Antes de permitir la aprobación, el sistema deberá verificar:

- La OP existe.
- La OP pertenece al proyecto correspondiente.
- Producción ha registrado la terminación.
- Existe una inspección.
- La inspección tiene un resultado.
- Se registraron las cantidades inspeccionadas.
- Se registraron las cantidades aprobadas y rechazadas.
- La información obligatoria está completa.
- No existen requisitos pendientes que impidan la aprobación.

---

## 4. Aprobación

Cuando Calidad determine que el producto cumple los requisitos, podrá seleccionar:

APROBAR OP

El sistema deberá solicitar confirmación antes de ejecutar la acción.

---

## 5. Información registrada

Al aprobar una OP se deberá registrar:

- Número de OP.
- Proyecto.
- Inspector.
- Usuario que aprueba.
- Fecha.
- Hora.
- Resultado.
- Cantidad inspeccionada.
- Cantidad aprobada.
- Cantidad rechazada.
- Observaciones.
- Número de plano.
- Revisión del plano.

---

## 6. Cambio de estado

Cuando la aprobación sea válida:

PENDIENTE DE CALIDAD
        ↓
APROBADA POR CALIDAD
        ↓
PERMITE CIERRE DE OP

La aprobación de Calidad NO significa que la OP quede cerrada automáticamente.

La aprobación habilita el siguiente paso del proceso.

---

## 7. Rechazo

Si Calidad determina que la OP no cumple los requisitos:

PENDIENTE DE CALIDAD
        ↓
RECHAZADA
        ↓
CORRECCIÓN
        ↓
REINSPECCIÓN

El sistema deberá registrar el motivo del rechazo.

---

## 8. Regla crítica de cierre

### BLOQUEO DE CIERRE

El sistema NO permitirá cerrar una Orden de Producción si no existe una aprobación válida registrada por Calidad.

La validación deberá ejecutarse en el servidor, no solamente en la interfaz.

Mensaje propuesto:

"NO SE PUEDE CERRAR LA OP. La Orden de Producción requiere aprobación de Calidad."

---

## 9. Intento de cierre sin aprobación

Si un usuario intenta cerrar una OP sin aprobación de Calidad:

El sistema deberá:

1. Bloquear la operación.
2. No modificar el estado de la OP.
3. Mostrar el motivo del bloqueo.
4. Registrar el intento en la auditoría, si corresponde según la política de auditoría.

---

## 10. Rechazo y corrección

Cuando una OP sea rechazada:

- La OP no podrá cerrarse.
- Se deberá registrar la no conformidad cuando corresponda.
- Producción deberá realizar las correcciones necesarias.
- Calidad deberá realizar una nueva inspección.
- La nueva inspección deberá quedar relacionada con la anterior.

---

## 11. Reinspección

Una OP corregida podrá pasar nuevamente a inspección.

La reinspección deberá conservar el historial de inspecciones anteriores.

Ejemplo:

INSPECCIÓN 001
→ RECHAZADA

CORRECCIÓN

INSPECCIÓN 002
→ APROBADA

El sistema no deberá eliminar la inspección anterior.

---

## 12. Trazabilidad

La aprobación deberá registrar:

- Usuario.
- Fecha.
- Hora.
- OP.
- Inspección.
- Resultado.
- Estado anterior.
- Estado nuevo.
- Observaciones.

---

## 13. Regla fundamental

CALIDAD APRUEBA.

EL SISTEMA HABILITA EL CIERRE.

EL CIERRE DE LA OP SE REALIZA EN EL FLUJO DEFINIDO PARA PRODUCCIÓN.

NINGÚN USUARIO DEBE PODER SALTARSE LA VALIDACIÓN DE CALIDAD.