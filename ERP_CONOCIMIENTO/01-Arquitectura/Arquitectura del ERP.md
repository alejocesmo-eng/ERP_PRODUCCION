---
tipo: arquitectura
estado: borrador
version: 0.1
---
---
tipo: arquitectura
codigo: ARQ-SIST-001
nombre: Arquitectura General del Sistema ERP (Fase 1 - Fase 3)
fase: F1-F5
estado: en_revision
autor: Arquitecto de Software Senior
stack: Python 3.11+ / FastAPI / PostgreSQL / WebSockets
sistema_destino: ERP FastAPI + PostgreSQL
---

# Arquitectura General del Sistema ERP (Fase 1 - Fase 3)

## 1. Visión General de la Arquitectura
El ERP está diseñado bajo una arquitectura modular y desacoplada pero monolítica en despliegue (Monolito Modular con FastAPI), priorizando el rendimiento en tiempo real para el taller CNC y la integridad referencial en PostgreSQL desde la Fase 1.

### Principios Arquitectónicos
1. **Estrategia Database-First Robust (PostgreSQL)**: La base de datos relacional define el modelo de dominio desde la Fase 1. Los esquemas y claves foráneas prevén las Fases 2 (Compras/Proveedores) y 3 (BOM/Rutas/Maquinaria) sin requerir reestructuraciones destructivas.
2. **Control de Tiempos Dual (Diseño y Producción)**: 
   - **Tiempos en Diseño**: Estimación/Meta fijada por el Líder + Cronometraje activo desde que el dibujante inicia la tarea.
   - **Tiempos en Producción**: Sincronización con turno laboral, conmutación estricta Setup $\rightarrow$ Mecanizado.
3. **Seguridad y Acceso Temporal a Planos**: Cero persistencia local de planos en clientes. Servido mediante API REST protegida con tokens JWT temporales (TTL) vinculados al estado activo de la OP.
4. **Comunicación en Tiempo Real**: WebSockets nativos en FastAPI para la actualización instantánea del panel de Líderes y cronómetros de puesto de trabajo.

---

## 2. Diagrama de la Arquitectura de Software

```mermaid
graph TD
    subgraph Frontend / Planta & Oficina
        A[Puesto Trabajo CNC - UI Browser/Tablet]
        B[Panel Líder Producción / Diseño]
        C[Módulo Calidad / Metrología]
    end

    subgraph Backend FastAPI (Python)
        D[API Gateway / Router FastAPI]
        E[Módulo Autenticación & RBAC]
        F[Módulo Diseño & Tiempos Estimados]
        G[Módulo Producción & WebSockets Tiempos]
        H[Módulo Calidad & Informes TT]
        I[Módulo Inventario & Herramental]
    end

    subgraph Capa de Persistencia & Archivos
        J[(PostgreSQL Database)]
        K[Almacenamiento Seguro de Planos PDF/PNG]
    end

    A <-->|WebSockets / REST JWT| D
    B <-->|REST API / WebSockets| D
    C <-->|REST API| D

    D --> E
    D --> F
    D --> G
    D --> H
    D --> I

    E --> J
    F --> J
    G --> J
    H --> J
    I --> J

    F -->|Lectura/Escritura Planos| K
    G -->|Tokens Temporales TTL| K
# Arquitectura del ERP

## Estado actual verificado
Completar después de inspeccionar el repositorio.

## Módulos
- 

## Stack tecnológico
- Frontend:
- Backend:
- Base de datos:
- Autenticación/autorización:
- Pruebas:
- Despliegue:

## Principios
- Modularidad y límites explícitos.
- Integridad y trazabilidad de datos.
- Control de acceso por rol.
- Pruebas automatizadas para reglas críticas.
- Cambios pequeños y revisables.

## Decisiones relacionadas
- 
### Regla de Negocio: Excepción por Desviación de Tiempo en Setup
- **Condición**: Si el tiempo real acumulado en estado `En Setup` supera en un **50%** el tiempo estándar presupuestado para la operación.
- **Acción del ERP**: Al momento en que el operario presione el botón `Iniciar Mecanizado`, la pantalla no bloqueará el avance, pero desplegará un menú obligatorio de justificación con las siguientes opciones predefinidas:
  1. *Ajuste/centrado complejo de pieza o herramental.*
  2. *Espera por verificación de herramientas / insertos.*
  3. *Inconsistencia / aclaración de plano con Diseño.*
  4. *Falla / mantenimiento menor en máquina.*
  5. *Otro (requiere campo de texto breve).*
- **Persistencia**: La razón seleccionada se guardará en la tabla `registro_tiempos_produccion` en el campo `observacion_desviacion` para su posterior análisis en KPIs.
## Riesgos y preguntas



-

-- 1. USUARIOS Y ROLES (Fase 1 Core)
CREATE TYPE rol_usuario AS ENUM ('ADMINISTRADOR', 'JEFE_AREA', 'ALMACENISTA', 'OPERARIO', 'CONSULTA');

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    rol rol_usuario NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. AREAS Y PUESTOS DE TRABAJO / MÁQUINAS
CREATE TABLE estaciones_trabajo (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL, -- Ej: CNC-01, MCR-02
    nombre VARCHAR(100) NOT NULL,
    area VARCHAR(30) NOT NULL, -- SERVICIOS (100), METALISTERIA (300), MECANIZADOS (400)
    activa BOOLEAN DEFAULT TRUE
);

-- 3. ÓRDENES DE PRODUCCIÓN (OP)
CREATE TYPE estado_op AS ENUM (
    'PLANIFICADA', 'PROGRAMADA', 'EN_DISENO', 'LIBERADA', 
    'EN_PROCESO_CNC', 'EN_CALIDAD', 'EN_TRATAMIENTO_TERMICO', 'COMPLETADA', 'CANCELADA'
);

CREATE TABLE ordenes_produccion (
    id SERIAL PRIMARY KEY,
    consecutivo_op VARCHAR(20) UNIQUE NOT NULL, -- 100XXXX, 300XXXX, 400XXXX
    pedido_comercial_id VARCHAR(50) NOT NULL,
    descripcion_pieza TEXT NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    estado estado_op DEFAULT 'PLANIFICADA',
    dibujante_asignado_id INT REFERENCES usuarios(id),
    motivo_planificacion TEXT, -- Para medición de días retenido en Planificada
    fecha_apertura TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_liberacion TIMESTAMP WITH TIME ZONE
);

-- 4. CONTROL DE TIEMPOS DE DISEÑO (Requisito Especifico)
CREATE TABLE tiempos_diseno (
    id SERIAL PRIMARY KEY,
    orden_produccion_id INT REFERENCES ordenes_produccion(id) ON DELETE CASCADE,
    dibujante_id INT REFERENCES usuarios(id),
    tiempo_estimado_horas NUMERIC(5,2) NOT NULL, -- Propuesto por el Líder de Diseño
    fecha_hora_inicio TIMESTAMP WITH TIME ZONE, -- Inicia al poner la OP "En Diseño"
    fecha_hora_fin TIMESTAMP WITH TIME ZONE,
    segundos_reales_acumulados INT DEFAULT 0,
    cumplio_meta BOOLEAN
);

-- 5. PLANOS Y DOCUMENTACIÓN TÉCNICA
CREATE TABLE planos_op (
    id SERIAL PRIMARY KEY,
    orden_produccion_id INT REFERENCES ordenes_produccion(id) ON DELETE CASCADE,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_almacenamiento VARCHAR(512) NOT NULL,
    version INT DEFAULT 1,
    subido_por INT REFERENCES usuarios(id),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. CONTROL DE TIEMPOS DE PRODUCCIÓN (Puesto CNC / Turnos)
CREATE TYPE tipo_tiempo_prod AS ENUM ('SETUP', 'MECANIZADO');

CREATE TABLE registro_tiempos_produccion (
    id SERIAL PRIMARY KEY,
    orden_produccion_id INT REFERENCES ordenes_produccion(id),
    operario_id INT REFERENCES usuarios(id),
    estacion_id INT REFERENCES estaciones_trabajo(id),
    tipo_tiempo tipo_tiempo_prod NOT NULL,
    fecha_hora_inicio TIMESTAMP WITH TIME ZONE NOT NULL,
    fecha_hora_fin TIMESTAMP WITH TIME ZONE,
    segundos_ejecutados INT DEFAULT 0,
    pausado_por_turno BOOLEAN DEFAULT FALSE
);
