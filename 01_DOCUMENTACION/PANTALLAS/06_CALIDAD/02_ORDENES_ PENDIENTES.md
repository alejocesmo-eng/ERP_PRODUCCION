# ÓRDENES DE PRODUCCIÓN PENDIENTES DE CALIDAD

## 1. Objetivo

Esta pantalla permite consultar y gestionar las Órdenes de Producción que requieren intervención de Calidad.

La pantalla será el punto principal de entrada para iniciar las inspecciones.

---

## 2. Acceso

Permiso mínimo:

- CALIDAD_VER

Las acciones disponibles dependerán de los permisos específicos del usuario.

---

## 3. Información de la lista

La tabla deberá mostrar como mínimo:

| Campo | Descripción |
|---|---|
| OP | Número de Orden de Producción |
| Proyecto | Proyecto relacionado |
| Cliente | Cliente del proyecto |
| Producto | Producto fabricado |
| Cantidad | Cantidad producida |
| Fecha producción | Fecha de terminación |
| Estado | Estado de Calidad |
| Prioridad | Prioridad de atención |
| Inspector | Usuario asignado, si aplica |

---

## 4. Estados

La pantalla podrá mostrar OP en los siguientes estados:

- PENDIENTE
- EN INSPECCIÓN
- APROBADA
- RECHAZADA
- PENDIENTE DE CORRECCIÓN
- REINSPECCIÓN

---

## 5. Filtros

El usuario podrá filtrar por:

- Número de OP.
- Proyecto.
- Cliente.
- Producto.
- Estado.
- Fecha.
- Prioridad.
- Inspector.

---

## 6. Búsqueda

El usuario podrá buscar utilizando:

- Número de OP.
- Número de proyecto.
- Cliente.
- Producto.

La búsqueda deberá permitir localizar rápidamente una OP.

---

## 7. Acciones

Según el estado y los permisos del usuario, se podrán realizar las siguientes acciones:

### Ver OP

Permite consultar el expediente de la Orden de Producción.

### Iniciar inspección

Permite comenzar el proceso de inspección.

### Registrar resultado

Permite registrar el resultado de la inspección.

### Aprobar

Permite aprobar la OP cuando el resultado cumple los requisitos.

### Rechazar

Permite registrar un rechazo y generar el proceso correspondiente.

### Reinspeccionar

Permite realizar una nueva inspección después de una corrección.

---

## 8. Información disponible antes de inspeccionar

Antes de iniciar la inspección, Calidad deberá poder consultar:

- Datos del proyecto.
- Cliente.
- Información comercial relevante.
- Orden de Producción.
- Número de plano.
- Revisión del plano.
- Documentación técnica.
- Cantidad solicitada.
- Cantidad producida.
- Material utilizado.
- Registros de producción.
- Cantidad rechazada por Producción.
- Observaciones.

---

## 9. Regla de negocio

Una OP solo podrá entrar al proceso de Calidad cuando Producción haya registrado la terminación de la fabricación o la condición definida por la empresa para solicitar inspección.

La OP no podrá cerrarse desde esta pantalla directamente.

El cierre será realizado por el flujo correspondiente después de la aprobación de Calidad.

---

## 10. Trazabilidad

El sistema deberá registrar:

- Usuario.
- Fecha.
- Hora.
- OP.
- Acción.
- Estado anterior.
- Estado nuevo.
- Observaciones.