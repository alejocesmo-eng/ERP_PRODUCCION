# Sistema de Gestión Integral — Instrucciones del Proyecto

## Misión
Desarrollar y refactorizar un ERP modular para manufactura CNC y equipos de la industria de alimentos, reflejando los procesos reales de la empresa, fortaleciendo la gestión de calidad (ISO 9001:2015), asegurando la trazabilidad total y permitiendo la mejora continua.

---

## Fuente de Verdad y Jerarquía de Autoridad
1. **Comportamiento Implementado**: El código fuente en `/src` o `/04_CODIGO` y las pruebas ejecutables en `/tests`.
2. **Especificación Funcional y Gobierno**: La bóveda `ERP_CONOCIMIENTO/` en Obsidian (Requisitos, Procesos, ADRs, Casos de Prueba).
3. **Diagnóstico y Mapa de Brechas**: La auditoría técnica `Arquitectura_y_Mapeo_SGI_ERP_v0.1.pdf`.
4. **Base de Datos Canónica**: El script unificado `ERP_CONOCIMIENTO/05-Desarrollo/schema_init_completo.sql`.

*Regla Directiva:* Si existen contradicciones entre la documentación, la base de datos y el código actual, identifícalas explícitamente y solicita resolución antes de asumir supuestos. No inventes procesos, reglas de negocio ni estados que no estén documentados.

---

## Método de Trabajo
1. **Comprender el Objetivo de Negocio**: Consultar los requerimientos (`REQ-*`) y decisiones (`ADR-*`) antes de escribir código.
2. **Inspección Previa**: Inspeccionar el código y los modelos existentes antes de realizar modificaciones.
3. **Plan Proporcional**: Proponer un plan claro identificando impactos, riesgos y dependencias.
4. **Refactorización y Desarrollo Iterativo**: Implementar cambios pequeños, coherentes y desacoplados.
5. **Ejecución de Pruebas**: Correr la suite de pruebas unitarias/integración correspondientes (`pytest` / `httpx`).
6. **Cierre y Documentación**: Documentar los resultados, registrar decisiones y actualizar la matriz de trazabilidad.

---

## Prioridades Técnicas y Reglas de Desarrollo

### 1. Resolución de Brechas Prioritarias (P0 / P1)
- **Homologación DDL vs ORM**: Asegurar paridad estricta de tipos de datos, llaves primarias (`SERIAL` vs `UUID`) y restricciones entre `schema_init_completo.sql` y los modelos de SQLAlchemy en `app/models/`.
- **Registro Explícito de Routers**: Garantizar que todos los endpoints (`ordenes.py`, `almacen.py`, `calidad.py`, `trazabilidad.py`) estén registrados explícitamente en `app/main.py` vía `app.include_router(...)`.
- **Persistencia Real**: Eliminar almacenes simulados en memoria (ej. `MEMORIA_NC` en `calidad.py`) e implementar transacciones asíncronas reales sobre PostgreSQL.

### 2. Reglas de Negocio Core (Taller CNC y Calidad)
- **Control de Tiempos Dual**:
  - *Diseño*: Medición automática al pasar a estado `EN_DISENO` frente al tiempo estimado por el Líder.
  - *Producción*: Conmutación estricta `Setup` $\rightarrow$ `Mecanizado` sincronizada con el turno. Solicitar justificación obligatoria en `observacion_desviacion` ante excesos $>50\%$ en Setup (ADR-001).
- **Seguridad de Planos**: Servir planos técnicos mediante tokens de lectura temporales (TTL) vinculados al estado activo de la OP en el puesto de trabajo.
- **Calidad e ISO 9001:2015**:
  - Inspección metrológica previa a la liberación de la OP (ISO 8.6).
  - Evidencia fotográfica obligatoria antes de autorizar envíos por email a Tratamiento Térmico (ISO 8.5.1).
  - Emisión de No Conformidades (`NC-AAAA-XXXX`) que bloqueen el Cierre de la OP e inicien la re-solicitud automática de materia prima a Compras (ISO 8.7).

### 3. Calidad del Software
- Usar arquitectura asíncrona pura (`async/await`) con `SQLAlchemy 2.0` / `SQLModel` y `asyncpg`.
- Validar todas las entradas y salidas con esquemas estrictos de `Pydantic v2`.
- Reutilizar componentes y patrones existentes; evitar duplicidad de lógica.
- Validar permisos de rol (`ADMINISTRADOR`, `JEFE_AREA`, `ALMACENISTA`, `OPERARIO`, `CONSULTA`) en cada endpoint.
- **Transparencia en Pruebas**: No afirmar que una prueba pasó si no se ejecutó. No ocultar errores, limitaciones ni pendientes.

---

## Control de Cambios
- No sobrescribir ni eliminar trabajo existente sin justificación técnica.
- No ejecutar migraciones destructivas sobre la base de datos sin autorización explícita y plan de reversión (`alembic downgrade`).
- No introducir dependencias externas sin evaluar su peso e impacto en el proyecto.
- Solicitar autorización antes de realizar operaciones irreversibles.

---

## Formato de Entrega
Al finalizar cada tarea o módulo, entregar un resumen con:
1. **Qué cambió**: Lista de archivos modificados/creados (`app/`, `tests/`, `alembic/`).
2. **Por qué**: Vínculo con el requerimiento (`REQ-*`), ADR o hallazgo técnico del proyecto.
3. **Pruebas ejecutadas**: Comandos corridos y sus resultados reales (código HTTP, aserciones).
4. **Pendientes**: Asuntos o reglas por validar con los responsables de área.

## Skills Disponibles en `.agent/skills/`
- `obsidian-markdown`: Aplica sintaxis nativa de Obsidian (YAML Frontmatter estricto y wikilinks `[[...]]`) en la bóveda `ERP-CONOCIMIENTO/`.
- `defuddle`: Limpia y resume texto externo para optimizar el consumo de tokens.