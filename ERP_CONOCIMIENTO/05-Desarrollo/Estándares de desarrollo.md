---
tipo: estándar
estado: propuesto
---
---
tipo: desarrollo
codigo: DEV-STD-001
nombre: Guía Técnica de Entorno, Estándares de Desarrollo y Migraciones
fase: F1-F5
estado: aprobado
autor: Arquitecto de Software Senior
stack: Python 3.11+ / FastAPI / PostgreSQL 15+ / Docker / Alembic
sistema_destino: ERP FastAPI + PostgreSQL
---

# DEV-STD-001: Guía Técnica de Entorno, Estándares de Desarrollo y Migraciones

## 1. Propósito
Establecer la estructura de proyecto, patrones de codificación, flujo de migraciones de base de datos con Alembic, configuración de contenedores Docker y estándares de desarrollo backend en Python/FastAPI para el ERP de manufactura.

---

## 2. Configuración del Entorno Local de Desarrollo (Docker Compose)

Para garantizar un entorno reproducible, la base de datos PostgreSQL y la gestión de archivos se ejecutan en Docker local.

### 2.1. Archivo `docker-compose.yml`
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: erp_postgres
    restart: always
    environment:
      POSTGRES_USER: erp_admin
      POSTGRES_PASSWORD: erp_password_2026
      POSTGRES_DB: erp_manufactura
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/schema_init_completo.sql:/docker-entrypoint-initdb.d/init.sql

  api:
    build: .
    container_name: erp_fastapi
    restart: always
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://erp_admin:erp_password_2026@db:5432/erp_manufactura
      JWT_SECRET_KEY: super_secret_jwt_key_manufactura_2026
    volumes:
      - .:/app
      - planos_storage:/app/storage/planos
    depends_on:
      - db

volumes:
  postgres_data:
  planos_storage:
# Estándares de desarrollo

## Por confirmar tras inspección del repositorio
- Convenciones de nombres:
- Estructura de módulos:
- Manejo de errores:
- Validación:
- Logging y auditoría:
- Acceso a datos:
- Seguridad:
- Pruebas:
- Migraciones:
- Documentación:

## Regla
No introducir una convención nueva antes de comprobar si ya existe una convención funcional en el proyecto.
