# MÓDULO PRODUCCIÓN

## 1. Objetivo

El módulo de Producción permitirá consultar, ejecutar y controlar las Órdenes de Producción (OP) que hayan sido liberadas por el sistema.

El módulo deberá proporcionar a Producción la información necesaria para fabricar un proyecto, incluyendo planos, materiales, cantidades, consumos, registros de producción y estado de la OP.

---

# 2. Acceso

El acceso al módulo estará controlado mediante roles y permisos.

El personal de Producción podrá consultar y ejecutar las OP que se encuentren autorizadas para producción.

Producción no podrá:

* Crear o modificar el diseño técnico.
* Modificar los planos vigentes.
* Liberar una OP.
* Modificar materiales definidos por Diseño.
* Autorizar cambios de una OP liberada.

Los cambios posteriores a la liberación de una OP deberán seguir el proceso de aprobación correspondiente.

---

# 3. Dashboard de Producción

## Objetivo

Mostrar un resumen de las actividades y órdenes que requieren atención.

## Información propuesta

* OP pendientes.
* OP liberadas.
* OP en producción.
* OP terminadas.
* OP que requieren atención.
* OP con material pendiente.
* OP con documentación pendiente.

## Acciones

* Consultar OP.
* Filtrar OP.
* Abrir detalle de OP.
* Consultar planos.
* Consultar materiales.

---

# 4. Órdenes de Producción

Producción podrá consultar las OP disponibles para su área.

## Información

* Número de OP.
* Proyecto.
* Número de plano.
* Revisión.
* Cantidad programada.
* Estado.
* Fecha de liberación.
* Fecha prevista de producción.

## Estados preliminares

* Liberada.
* En producción.
* Terminada.
* Cerrada.

Los estados definitivos se validarán durante el diseño detallado del proceso.

---

# 5. Detalle de la Orden de Producción

Cada OP deberá funcionar como un expediente de fabricación.

## Información relacionada

* Proyecto.
* Cliente.
* Información de venta.
* Confirmación del cliente.
* Número de plano.
* Revisión vigente.
* Documentación.
* Material requerido.
* Material entregado.
* Material pendiente.
* Consumos.
* Cantidad programada.
* Cantidad producida.
* Cantidad rechazada.
* Cantidad pendiente.
* Observaciones.
* Historial.
* Auditoría.

---

# 6. Planos

Producción deberá tener acceso al plano correspondiente a la OP.

El sistema deberá identificar claramente:

* Número de plano.
* Revisión.
* Estado.
* Fecha.
* Proyecto relacionado.
* OP relacionada.

## Propuesta de control de entrega y seguimiento

Se propone estudiar la utilización de un código de barras asociado al plano para registrar su entrega y seguimiento.

Flujo propuesto:

Generación → Entrega → Recepción → Consulta → Reemplazo

Esta funcionalidad queda como:

**PROPUESTA — PENDIENTE DE APROBACIÓN**

El mecanismo definitivo, tipo de código, lectores, puntos de escaneo y reglas de seguimiento serán definidos posteriormente.

---

# 7. Materiales recibidos

Producción deberá poder consultar el material que corresponde a cada OP.

El sistema deberá diferenciar entre:

* Material requerido.
* Material disponible.
* Material reservado.
* Material entregado.
* Material pendiente.

## Entregas parciales

Se permite realizar entregas parciales de material.

Ejemplo:

Material requerido: 100 kg.

Primera entrega: 60 kg.

Segunda entrega: 40 kg.

Resultado:

Material requerido: 100 kg.
Material entregado: 100 kg.
Material pendiente: 0 kg.

Todas las entregas deberán quedar registradas y asociadas a la OP.

---

# 8. Inicio de producción

Antes de iniciar la producción, el sistema deberá realizar las validaciones correspondientes.

Como mínimo deberá verificar:

* OP liberada.
* Plano disponible.
* Información técnica disponible.
* Material requerido disponible según las reglas definidas.

Si los requisitos no se cumplen, el sistema deberá informar el motivo y bloquear la acción cuando corresponda.

La regla exacta para iniciar producción cuando existen entregas parciales queda pendiente de definición detallada.

---

# 9. Registro de producción

Producción podrá registrar los resultados obtenidos durante la fabricación.

## Información preliminar

* OP.
* Fecha.
* Usuario.
* Cantidad producida buena.
* Cantidad rechazada.
* Cantidad pendiente.
* Observaciones.

Ejemplo:

Cantidad programada: 25 unidades.

Cantidad buena: 20 unidades.

Cantidad rechazada: 2 unidades.

Cantidad pendiente: 3 unidades.

El sistema deberá calcular y controlar las cantidades para evitar inconsistencias.

---

# 10. Cierre de OP

Cuando se complete la fabricación, el usuario autorizado podrá solicitar o ejecutar el cierre de la OP según las reglas que se definan posteriormente.

Antes del cierre se deberá verificar, como mínimo:

* Cantidad producida.
* Cantidad rechazada.
* Cantidad pendiente.
* Consumo de materiales.
* Información requerida.
* Observaciones necesarias.

Estado preliminar:

EN PRODUCCIÓN → TERMINADA → CERRADA

La existencia de una etapa de verificación o calidad entre TERMINADA y CERRADA queda pendiente de definición.

---

# 11. Cambios posteriores a la liberación

Una OP liberada representa una versión técnica autorizada del proyecto para producción.

No se deberán realizar modificaciones silenciosas sobre información crítica.

Los cambios posteriores a la liberación deberán seguir un proceso de aprobación.

## Responsable de autorización

**Jefe de Producción.**

## Flujo preliminar

OP liberada
↓
Solicitud de cambio
↓
Evaluación
↓
Aprobación o rechazo
↓
Si se aprueba: nueva revisión
↓
Nueva validación
↓
Nueva liberación

Los detalles del proceso de cambios serán desarrollados posteriormente.

---

# 12. Trazabilidad

Las acciones relevantes deberán registrar:

* Usuario.
* Fecha.
* Hora.
* Acción realizada.
* Estado anterior.
* Estado nuevo.
* OP relacionada.
* Observaciones cuando correspondan.

El sistema deberá permitir consultar el historial de una OP.

---

# 13. Principio general

Producción debe recibir una OP técnicamente autorizada y disponer de la información necesaria para ejecutar el trabajo.

El sistema debe evitar que se produzca utilizando información desactualizada, una OP no autorizada o documentación incorrecta.

---

# 14. Elementos pendientes de definición detallada

Los siguientes puntos quedan abiertos para una segunda etapa de análisis:

1. Reglas exactas para iniciar producción con entregas parciales.
2. Proceso detallado de consumo de materiales.
3. Registro de desperdicios y sobrantes.
4. Gestión detallada de retales.
5. Sistema definitivo de identificación y seguimiento de planos.
6. Integración con Calidad.
7. Estados definitivos de una OP.
8. Reglas de cierre.
9. Indicadores y reportes de Producción.
10. Gestión de cambios posteriores a la liberación.
