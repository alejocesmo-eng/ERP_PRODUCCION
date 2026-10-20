# REGLAS MAESTRAS DE DESARROLLO — SGI ERP

## 1. Objetivo

Construir un Sistema de Gestión Integral empresarial modular, trazable, seguro y escalable, conservando las funcionalidades existentes que estén correctas.

## 2. Arquitectura

* Frontend: React.
* Backend: Python y FastAPI.
* Base de datos: PostgreSQL.
* ORM: SQLAlchemy, sujeto a auditoría y aprobación del modelo oficial.
* API: mantener un contrato coherente y versionado.
* Las reglas de negocio deben validarse en el backend, no exclusivamente en el frontend.

## 3. Regla obligatoria: inspeccionar antes de modificar

Antes de editar:

1. Lee la documentación relevante.
2. Localiza los archivos, modelos, endpoints, servicios y pantallas implicados.
3. Identifica dependencias y comportamiento actual.
4. Presenta un plan breve de cambios.
5. Indica riesgos, archivos afectados y pruebas necesarias.

## 4. Prohibiciones

* No reescribir el proyecto completo para resolver un problema localizado.
* No crear tablas, endpoints o servicios duplicados.
* No cambiar relaciones o reglas de negocio por iniciativa propia.
* No borrar funcionalidades sin justificación y aprobación.
* No ejecutar migraciones destructivas ni modificar bases de datos productivas.
* No inventar procesos empresariales pendientes de confirmación.
* No afirmar que una funcionalidad funciona sin pruebas verificables.
* No exponer contraseñas, tokens, secretos ni datos reales en los informes.

## 5. Fuente de verdad

La documentación funcional aprobada define los procesos y las reglas.
El modelo de datos aprobado define las relaciones.
El contrato API aprobado define las interfaces.
Si existe una contradicción entre documentación y código, informa la discrepancia y espera una decisión antes de cambiarla.

## 6. Trazabilidad obligatoria

Cada funcionalidad debe vincular:
Proceso → Rol → Estado → Regla de negocio → Tabla → Servicio → Endpoint → Pantalla → Validación → Prueba.

## 7. Forma de trabajar

* Realizar cambios pequeños y revisables.
* Mantener los cambios dentro del alcance aprobado.
* Añadir o actualizar pruebas.
* Actualizar la documentación afectada.
* Informar archivos modificados, decisiones tomadas, resultados y riesgos pendientes.
* Detenerse si faltan requisitos que cambien sustancialmente el diseño.

## 8. Seguridad

* No almacenar contraseñas en texto plano.
* No incluir secretos reales en el código ni en documentación.
* Validar permisos en el backend.
* Mantener auditoría de operaciones críticas.
* Usar entornos de prueba y datos ficticios.
* No ejecutar operaciones irreversibles sin autorización explícita.

## 9. Criterio de finalización

Una tarea solo está terminada cuando:

1. Cumple los requisitos aprobados.
2. Las pruebas pertinentes se ejecutaron.
3. No introduce regresiones conocidas.
4. La documentación está actualizada.
5. Se entrega evidencia y se identifican las limitaciones restantes.
