# DASHBOARD DE CALIDAD

## 1. Objetivo

El Dashboard de Calidad permite visualizar de forma rápida el estado de las Órdenes de Producción relacionadas con el proceso de inspección y aprobación.

Su objetivo es mostrar qué órdenes requieren atención y facilitar el acceso a las inspecciones pendientes.

---

## 2. Acceso

El Dashboard estará disponible para usuarios que tengan permisos relacionados con Calidad.

Permisos mínimos:

- CALIDAD_VER

---

## 3. Información principal

El Dashboard deberá mostrar indicadores generales:

- OP pendientes de inspección.
- OP en inspección.
- OP aprobadas.
- OP rechazadas.
- OP pendientes de corrección.
- OP pendientes de reinspección.
- No conformidades abiertas.

---

## 4. Indicadores

Ejemplo:

| Indicador | Cantidad |
|---|---:|
| Pendientes de inspección | 5 |
| En inspección | 2 |
| Aprobadas | 18 |
| Rechazadas | 3 |
| Pendientes de corrección | 2 |
| Pendientes de reinspección | 1 |
| No conformidades abiertas | 4 |

Los valores serán calculados automáticamente por el sistema.

---

## 5. Órdenes que requieren atención

El Dashboard deberá mostrar una lista de las OP que requieren intervención de Calidad.

Información mínima:

- Número de OP.
- Proyecto.
- Cliente.
- Producto.
- Cantidad.
- Fecha de terminación de producción.
- Estado.
- Prioridad.
- Fecha requerida de inspección.

La ventana de Calidad de Producto también deberá permitir consultar el concentrado de todas las órdenes de producción abiertas, excluyendo las órdenes cerradas o canceladas. Al abrir una OP se mostrarán sus datos comerciales, producto, cantidad, estado, avance, fechas, materiales, observaciones y componentes asociados. Cuando exista un plano PDF cargado, deberá poder visualizarse desde el detalle de la orden.

---

## 6. Acciones

Desde el Dashboard el usuario podrá:

- Consultar y buscar órdenes abiertas.
- Abrir una OP.
- Iniciar inspección.
- Consultar información técnica.
- Visualizar el plano PDF de una OP.
- Consultar materiales.
- Consultar producción.
- Registrar inspección.
- Consultar no conformidades.
- Realizar reinspección cuando corresponda.

Las acciones disponibles dependerán de los permisos del usuario.

---

## 7. Filtros

El usuario podrá filtrar por:

- Estado.
- Número de OP.
- Proyecto.
- Cliente.
- Producto.
- Fecha.
- Prioridad.
- Inspector.

---

## 8. Ordenamiento

La lista podrá ordenarse por:

- Fecha de terminación.
- Fecha de solicitud de inspección.
- Prioridad.
- Número de OP.
- Estado.

---

## 9. Regla de negocio

Una OP terminada por Producción deberá aparecer en el Dashboard de Calidad cuando requiera inspección.

Una OP aprobada deberá dejar de aparecer como pendiente de inspección.

Una OP rechazada deberá permanecer visible hasta que se complete el proceso correspondiente de corrección y reinspección.

---

## 10. Trazabilidad

Las acciones realizadas desde el Dashboard deberán quedar registradas en la auditoría del sistema.

Como mínimo:

- Usuario.
- Fecha.
- Hora.
- Acción.
- OP.
- Estado anterior.
- Estado nuevo.