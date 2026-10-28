---
tipo: gobierno
codigo: GOB-EST-001
nombre: Estándares de Gobierno, Desarrollo e Integración para Agentes de IA
fase: F1-F5
estado: aprobado
version: 1.1
autor: Analista Funcional y Arquitecto de Software Senior
sistema_destino: ERP FastAPI + PostgreSQL
---

# GOB-EST-001: Estándares de Gobierno, Desarrollo e Integración para Agentes de IA

## 1. Visión General de Gobierno
Este documento establece las directrices de gobernanza técnica, arquitectura de información y estándares de código para la bóveda `ERP_CONOCIMIENTO`. Su objetivo principal es asegurar la integridad del conocimiento y permitir que desarrolladores y agentes de IA (como AntiGravity) trabajen con estándares profesionales sin introducir deuda técnica o ambigüedades en la base de datos PostgreSQL y la API en FastAPI.

---

## 2. Reglas Directivas para el Desarrollo y Agentes de IA

1. **Gestión de Estados de Documentación**: Todo archivo en la bóveda debe mantener en su frontmatter el estado correspondiente (`borrador`, `en_revision`, `aprobado`, `obsolete`).
2. **Seguridad y Confidencialidad**: Prohibido estrictamente almacenar credenciales, tokens JWT estáticos, claves de PostgreSQL o variables de entorno (`.env`) dentro de las notas de Obsidian.
3. **No Duplicidad de Código**: Las notas de Obsidian documentan especificaciones, esquemas DDL y reglas de negocio[cite: 2, 4]. El código ejecutable reside en el repositorio backend (`/app`) y las migraciones en `/alembic`.
4. **Trazabilidad de Decisiones (ADR)**: Cualquier cambio en las reglas de negocio (ej. excepciones de tiempos de Setup, control metrológico o flujo de No Conformidades) debe registrarse mediante un nuevo archivo en `08-Decisiones/`.
5. **Formato de Enlaces de Obsidian**: Mantener el uso de wikilinks (`[[Nombre del Archivo]]`) para preservar el grafo de conocimiento activo en la bóveda.

---

## 3. Estándares Técnicos para el Desarrollo (FastAPI + PostgreSQL)

### 3.1. Normas de Base de Datos (PostgreSQL)
- **Nomenclatura**: Nombres de tablas, columnas y tipos `ENUM` en minúsculas y snake_case (ej. `ordenes_produccion`, `tiempo_estimado_horas`).
- **Llaves Primarias y Foráneas**: Uso obligatorio de `id SERIAL PRIMARY KEY` e integridad referencial estricta mediante `REFERENCES` para evitar registros huérfanos.
- **Auditoría de Registros**: Tablas operativas deben incluir campos de timestamp con zona horaria: `creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`.

### 3.2. Normas de Backend (Python 3.11+ / FastAPI)
- **Modelado Asíncrono**: Uso de `async/await` con `asyncpg` y `SQLAlchemy 2.0` / `SQLModel` para los endpoints de FastAPI y los handlers de WebSockets.
- **Validación con Pydantic**: Toda entrada y salida de API REST debe validarse estrictamente mediante esquemas Pydantic v2.
- **Manejo de Respuestas HTTP**:
  - `200 OK` / `201 Created`: Operaciones exitosas.
  - `400 Bad Request`: Violación de reglas de negocio (ej. intentar cerrar una OP con No Conformidades activas).
  - `403 Forbidden`: Expiración o invalidez de tokens de acceso temporal a planos.
  - `422 Unprocessable Entity`: Error de validación de datos (ej. enviar informe de Tratamiento Térmico sin foto).



---
## Enlaces de Gobierno
- [[Inicio]]
- [[Mapa de procesos]]
---

## 4. Índice General de la Bóveda (`00-Gobierno/Inicio.md`)



```mermaid
graph TD
    A[[00-Gobierno/Inicio]] --> B[[01-Arquitectura/Arquitectura del ERP]]
    A --> C[[02-Procesos/Mapa de procesos]]
    A --> D[[03-Requisitos/REQ-PROD-001 - Puesto CNC]]
    A --> E[[04-Calidad-ISO/PRO-CAL-001 - Metrologia y NC]]
    A --> F[[06-Pruebas/TC-PROD-001 - Pruebas CNC]]
    A --> G[[08-Decisiones/ADR-001 - Tiempos y Setup]]
    
       