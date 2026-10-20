# MÓDULO DE CALIDAD

## 1. Objetivo

El módulo de Calidad tiene como objetivo controlar la inspección y aprobación de los productos fabricados antes del cierre de una Orden de Producción (OP).

El módulo permitirá registrar inspecciones, resultados, observaciones, no conformidades y la aprobación o rechazo de una Orden de Producción.

---

## 2. Alcance

El módulo contempla:

- Consulta de Órdenes de Producción terminadas.
- Recepción de productos para inspección.
- Registro de inspecciones.
- Registro de resultados.
- Registro de observaciones.
- Registro de no conformidades.
- Aprobación de la Orden de Producción.
- Rechazo de la Orden de Producción.
- Seguimiento de correcciones.
- Historial y trazabilidad de las inspecciones.
- Control de usuario, fecha y hora de cada acción.

---

## 3. Relación con Producción

Producción es responsable de fabricar y registrar la terminación de la Orden de Producción.

Calidad es responsable de verificar el cumplimiento de los requisitos definidos para el producto.

Una Orden de Producción no podrá ser cerrada hasta que Calidad haya registrado su aprobación.

Flujo:

Producción termina fabricación
        ↓
OP queda pendiente de inspección
        ↓
Calidad realiza inspección
        ↓
┌─────────────────────┐
│ Resultado inspección│
└─────────────────────┘
        ↓
   ┌───────────────┐
   │               │
APROBADA        RECHAZADA
   │               │
   ↓               ↓
Permite        Registrar
cierre OP      no conformidad
   │               │
   ↓               ↓
CERRAR OP      Corrección /
               nueva inspección

---

## 4. Estados propuestos

### Estado de inspección

- PENDIENTE
- EN INSPECCIÓN
- APROBADA
- RECHAZADA
- PENDIENTE DE CORRECCIÓN
- REINSPECCIÓN

### Estado de la OP

- EN PRODUCCIÓN
- PRODUCCIÓN TERMINADA
- PENDIENTE DE CALIDAD
- APROBADA POR CALIDAD
- RECHAZADA POR CALIDAD
- CERRADA

Los estados definitivos serán validados durante el diseño funcional.

---

## 5. Aprobación de Calidad

Para aprobar una OP, Calidad deberá registrar como mínimo:

- Orden de Producción.
- Proyecto.
- Producto.
- Cantidad inspeccionada.
- Cantidad aprobada.
- Cantidad rechazada.
- Resultado de inspección.
- Observaciones.
- Usuario responsable.
- Fecha y hora.

Cuando la inspección sea aprobada, el sistema deberá registrar:

- Usuario que aprobó.
- Fecha.
- Hora.
- Resultado.
- Observaciones.
- Versión/revisión de la OP inspeccionada.

---

## 6. Rechazo

Si Calidad determina que el producto no cumple los requisitos establecidos, la OP no podrá cerrarse.

El sistema deberá permitir registrar:

- Motivo del rechazo.
- Cantidad afectada.
- Descripción de la no conformidad.
- Evidencias o documentos.
- Observaciones.
- Responsable de la inspección.

La OP podrá pasar a un proceso de corrección y posteriormente a una nueva inspección.

---

## 7. Regla crítica del sistema

### REGLA DE CIERRE DE OP

Una Orden de Producción NO podrá pasar al estado CERRADA si:

- Calidad no ha realizado la inspección requerida.
- La inspección se encuentra rechazada.
- Existen no conformidades pendientes que impidan el cierre.
- No existe aprobación registrada por Calidad.

El sistema deberá bloquear la acción "CERRAR OP" cuando alguno de estos requisitos no se cumpla.

Mensaje propuesto:

"NO SE PUEDE CERRAR LA OP. La Orden de Producción requiere aprobación de Calidad."

---

## 8. Trazabilidad

Toda acción realizada por Calidad deberá quedar registrada.

Como mínimo:

- Usuario.
- Fecha.
- Hora.
- OP.
- Proyecto.
- Acción.
- Estado anterior.
- Estado nuevo.
- Resultado.
- Observaciones.

---

## 9. Permisos propuestos

CALIDAD_VER
CALIDAD_INSPECCIONAR
CALIDAD_APROBAR
CALIDAD_RECHAZAR
CALIDAD_CREAR_NO_CONFORMIDAD
CALIDAD_MODIFICAR_NO_CONFORMIDAD
CALIDAD_REINSPECCIONAR

Estos permisos serán asociados posteriormente a los roles correspondientes.

---

## 10. Relación con otros módulos

### Ventas
Proporciona información comercial y requisitos del cliente.

### Diseño
Proporciona planos, especificaciones y revisiones técnicas.

### Almacén
Registra materiales entregados y movimientos relacionados.

### Producción
Registra fabricación, cantidades producidas, rechazos y terminación de la producción.

### Calidad
Realiza la inspección y determina la aprobación o rechazo.

### Auditoría y Trazabilidad
Registra todas las acciones realizadas dentro del proceso.

---

## 11. Regla de negocio principal

PRODUCCIÓN FABRICA.

CALIDAD INSPECCIONA Y APRUEBA.

EL SISTEMA SOLO PERMITE CERRAR LA OP DESPUÉS DE LA APROBACIÓN DE CALIDAD.

## Aprobación de Calidad antes del cierre

Una vez que Producción termine la fabricación, la Orden de Producción pasará a estado:

PENDIENTE DE CALIDAD

La Orden de Producción deberá ser inspeccionada por Calidad.

Producción no podrá cerrar directamente la OP.

Flujo:

PRODUCCIÓN TERMINADA
        ↓
PENDIENTE DE CALIDAD
        ↓
     CALIDAD
        ↓
   ┌───────────┐
   │ Resultado │
   └───────────┘
      ↓     ↓
 APROBADA  RECHAZADA
    ↓         ↓
 CERRAR     CORREGIR /
    OP       REINSPECCIÓN

    ### Regla de bloqueo

El botón "CERRAR OP" deberá permanecer bloqueado mientras la Orden de Producción no tenga una aprobación válida registrada por Calidad.

Producción podrá consultar el resultado de Calidad, pero no podrá modificarlo.