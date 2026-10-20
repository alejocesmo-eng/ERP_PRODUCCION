# PROCESO PROYECTO → PRODUCCIÓN

## 1. Objetivo

Documentar el proceso mediante el cual un proyecto pasa desde el área de Ventas hasta Producción, incluyendo la evaluación y diseño, definición y solicitud de materiales, gestión de planos, generación y liberación de la Orden de Producción y entrega de materiales por parte del Almacén.

El objetivo del sistema será controlar el flujo, garantizar que la información necesaria esté disponible en cada etapa y mantener trazabilidad de las decisiones y operaciones realizadas.

---

# 2. Áreas involucradas

El proceso involucra inicialmente las siguientes áreas:

* Ventas
* Diseño
* Almacén
* Producción

Posteriormente podrán intervenir otras áreas, como Calidad, Compras, Mantenimiento y Costos.

---

# 3. Flujo actual del proceso

El flujo general identificado actualmente es:

Ventas
↓
Proyecto
↓
Diseño
↓
Evaluación y diseño
↓
Definición de materiales
↓
Solicitud de materiales
↓
Generación de Orden de Producción
↓
Producción

Paralelamente, el Almacén recibe, registra y suministra las materias primas necesarias para Producción.

---

# 4. Etapa 1 — Ventas

Ventas proporciona la información correspondiente al proyecto.

La información puede incluir:

* Cliente
* Proyecto
* Código o identificación del proyecto
* Descripción
* Cantidades
* Requerimientos del cliente
* Fecha requerida
* Documentación disponible
* Observaciones

## Resultado

El proyecto queda disponible para que Diseño pueda evaluarlo.

---

# 5. Etapa 2 — Evaluación por Diseño

Diseño recibe la información del proyecto y determina su viabilidad y requerimientos técnicos.

Actividades:

* Revisar información recibida.
* Analizar requerimientos.
* Determinar características del producto.
* Diseñar los componentes necesarios.
* Identificar materiales.
* Determinar cantidades.
* Generar o preparar planos.
* Identificar documentación necesaria para fabricación.

## Resultado

El proyecto cuenta con la información técnica necesaria para continuar con la preparación de producción.

---

# 6. Etapa 3 — Definición de materiales

Diseño determina los materiales necesarios para fabricar el proyecto.

Para cada material se deberá identificar, cuando aplique:

* Código.
* Descripción.
* Tipo.
* Material.
* Dimensiones.
* Cantidad.
* Unidad de medida.
* Especificaciones.
* Observaciones.

## Retales

Antes de solicitar material nuevo, el sistema deberá permitir verificar si existen retales disponibles que puedan utilizarse.

Ejemplo:

Material requerido:

Acero 304 — Ø50 mm × 250 mm

El sistema podrá mostrar retales compatibles disponibles.

Diseño podrá seleccionar un retal existente cuando cumpla las condiciones requeridas.

## Resultado

Queda definida la necesidad de materiales y, cuando sea posible, los materiales o retales que serán utilizados.

---

# 7. Etapa 4 — Solicitud de material

Diseño genera una solicitud de material asociada al proyecto y posteriormente a la Orden de Producción.

La solicitud deberá indicar:

* Proyecto.
* Orden de Producción, cuando corresponda.
* Material.
* Cantidad.
* Unidad.
* Especificaciones.
* Material nuevo o retal.
* Observaciones.
* Usuario solicitante.
* Fecha de solicitud.

## Resultado

La necesidad de material queda registrada formalmente en el sistema.

---

# 8. Etapa 5 — Documentación técnica y planos

Diseño deberá cargar o asociar al proyecto los planos y documentos necesarios para fabricación.

El sistema deberá permitir controlar:

* Documento.
* Tipo de documento.
* Número o código.
* Versión/revisión.
* Fecha.
* Usuario que lo cargó.
* Estado.
* Observaciones.

Cuando exista una nueva revisión de un plano, deberá conservarse la trazabilidad de las versiones anteriores.

## Regla propuesta

Una Orden de Producción no podrá ser liberada mientras no estén disponibles los planos y documentos técnicos requeridos.

---

# 9. Etapa 6 — Generación de la Orden de Producción

Una vez que Diseño haya completado la información necesaria, se genera la Orden de Producción.

La OP deberá estar relacionada con:

* Proyecto.
* Cliente.
* Producto.
* Cantidad.
* Materiales.
* Planos.
* Documentación técnica.
* Requerimientos especiales.
* Área responsable.
* Fechas.
* Usuario que la genera.

La OP inicialmente permanecerá en estado no liberado.

---

# 10. Etapa 7 — Validación para liberar la OP

Antes de liberar una Orden de Producción, el sistema deberá comprobar los requisitos definidos.

## Checklist de liberación

* [ ] Proyecto definido.
* [ ] Información técnica completa.
* [ ] Diseño terminado.
* [ ] Planos cargados.
* [ ] Revisión de planos definida.
* [ ] Materiales definidos.
* [ ] Solicitud de material realizada.
* [ ] Retales identificados o descartados.
* [ ] Información necesaria para Producción disponible.

## Regla

Si uno o más requisitos obligatorios están pendientes, el sistema deberá impedir la liberación de la Orden de Producción.

El sistema deberá indicar claramente qué requisito está pendiente.

Ejemplo:

> No se puede liberar la OP-0254 porque falta el plano de fabricación Rev. 02.

---

# 11. Etapa 8 — Liberación de la Orden de Producción

Cuando todos los requisitos obligatorios estén completos, un usuario autorizado de Diseño podrá liberar la OP.

La liberación deberá registrar:

* Usuario.
* Fecha.
* Hora.
* Estado anterior.
* Estado nuevo.
* Versión/revisión de documentación.
* Observaciones.

## Resultado

La Orden de Producción queda oficialmente disponible para Producción.

---

# 12. Etapa 9 — Recepción de materiales por Almacén

El Almacén recibe las materias primas y otros materiales.

Cada recepción deberá quedar registrada.

Información mínima:

* Material.
* Cantidad.
* Unidad.
* Fecha.
* Almacén.
* Ubicación.
* Documento de origen.
* Usuario responsable.
* Observaciones.

El ingreso deberá generar el movimiento correspondiente en inventario.

---

# 13. Etapa 10 — Entrega de materiales a Producción

Almacén suministra los materiales requeridos por Producción.

La entrega deberá estar asociada a:

* Orden de Producción.
* Proyecto.
* Material.
* Cantidad solicitada.
* Cantidad entregada.
* Almacén.
* Ubicación.
* Usuario que entrega.
* Usuario que recibe.
* Fecha y hora.

## Regla propuesta

El sistema deberá impedir la entrega de materiales a una Orden de Producción que no cumpla las condiciones establecidas para iniciar producción.

Como mínimo:

* OP liberada.
* Planos disponibles para Producción.
* Material solicitado.

El sistema deberá mostrar el motivo cuando una entrega esté bloqueada.

Ejemplo:

> Entrega bloqueada. La OP-0254 no ha sido liberada por Diseño.

---

# 14. Etapa 11 — Inicio de producción

Una vez liberada la OP y suministrados los materiales requeridos, Producción podrá iniciar el proceso de fabricación.

El sistema deberá registrar posteriormente:

* Inicio de producción.
* Usuario responsable.
* Cantidad producida.
* Cantidad pendiente.
* Consumos.
* Rechazos.
* Terminación.

Estos elementos serán desarrollados en el módulo de Producción.

---

# 15. Estados propuestos

El proyecto y la Orden de Producción deberán manejar estados.

Propuesta inicial:

```text
PROYECTO

Nuevo
↓
En evaluación
↓
En diseño
↓
Diseño terminado
↓
Listo para producción
↓
En producción
↓
Terminado
↓
Cerrado
```

La Orden de Producción podrá manejar:

```text
Borrador
↓
En preparación
↓
Pendiente de requisitos
↓
Lista para liberar
↓
Liberada
↓
En producción
↓
Terminada
↓
Cerrada
```

Los estados definitivos serán definidos durante el levantamiento de requisitos.

---

# 16. Reglas de negocio iniciales

## Regla 1 — Liberación

Diseño no podrá liberar una OP si existen requisitos obligatorios pendientes.

## Regla 2 — Planos

La OP deberá tener disponibles los planos y documentos técnicos requeridos antes de ser liberada.

## Regla 3 — Materiales

La OP deberá tener registrada la solicitud de materiales antes de poder ser liberada.

## Regla 4 — Retales

Cuando exista un retal compatible, deberá poder asociarse a la solicitud de material y reservarse para el proyecto.

## Regla 5 — Entrega

Almacén no podrá entregar materiales para una OP que no esté liberada, salvo que exista una excepción autorizada y registrada.

## Regla 6 — Trazabilidad

Toda acción relevante deberá registrar usuario, fecha y hora.

## Regla 7 — Documentación

Las revisiones de planos deberán conservarse para mantener trazabilidad histórica.

---

# 17. Información que todavía debemos confirmar

Este documento contiene el proceso identificado inicialmente. Antes de convertirlo en reglas definitivas del software será necesario confirmar con la empresa:

* ¿Quién crea formalmente el proyecto?
* ¿Ventas crea la solicitud o simplemente entrega información?
* ¿Quién crea la Orden de Producción?
* ¿Diseño puede modificar una OP después de liberarla?
* ¿Quién aprueba una OP?
* ¿Almacén puede entregar material antes de liberar una OP?
* ¿Se permite producción parcial?
* ¿Qué ocurre si no existe material suficiente?
* ¿Qué ocurre cuando se necesita comprar material?
* ¿Quién decide si un retal es técnicamente utilizable?
* ¿Cómo se identifica actualmente cada retal?
* ¿Qué documentos son obligatorios?
* ¿Producción debe confirmar que recibió los planos?
* ¿Quién puede cancelar una OP?
* ¿Quién puede modificar un plano después de iniciar producción?
* ¿Qué sucede cuando cambia la revisión de un plano?
* ¿Cómo se manejan sobrantes de material después de producción?
* ¿Cómo se registra actualmente el consumo de material?
* ¿Cómo se identifican actualmente los proyectos y órdenes de producción?

Estas preguntas deberán ser respondidas antes de cerrar el diseño definitivo del proceso.

---

# 18. Objetivo del sistema

El sistema deberá transformar el proceso actual en un flujo controlado y trazable:

```text
VENTAS
   ↓
PROYECTO
   ↓
DISEÑO
   ↓
PLANOS + MATERIALES
   ↓
SOLICITUD DE MATERIAL
   ↓
VALIDACIÓN
   ↓
LIBERACIÓN DE OP
   ↓
ALMACÉN
   ↓
ENTREGA DE MATERIAL
   ↓
PRODUCCIÓN
```

El sistema deberá impedir que una etapa avance cuando no se hayan cumplido los requisitos definidos y deberá indicar al usuario qué condición está pendiente.

---

# 19. Principio fundamental

El sistema no deberá limitarse a almacenar información.

Deberá utilizar la información registrada para **controlar el proceso**, evitar errores y garantizar trazabilidad.

Por ejemplo:

No solamente registrar:

> "Plano cargado."

Sino utilizar ese dato para determinar:

> "¿La Orden de Producción puede ser liberada?"

Y no solamente registrar:

> "Material disponible."

Sino utilizar esa información para determinar:

> "¿Puede Almacén entregar este material a Producción?"

Esto permitirá que el sistema funcione como una herramienta de control operativo y no únicamente como una base de datos.
