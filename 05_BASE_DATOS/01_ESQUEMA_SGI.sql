-- =============================================================================
-- ESQUEMA BASE DE DATOS — SISTEMA DE GESTIÓN INTEGRAL (SGI - ISO 9001:2026)
-- ARCHIVO: 05_BASE_DATOS/01_ESQUEMA_SGI.sql
-- =============================================================================

BEGIN;

-- 1. TIPOS ENUMERADOS (ESTADOS DE PROCESOS)
CREATE TYPE estado_proyecto AS ENUM ('BORRADOR', 'CONFIRMADO', 'EN_DISENO', 'FINALIZADO', 'CANCELADO');
CREATE TYPE estado_plano AS ENUM ('BORRADOR', 'EN_REVISION', 'APROBADO', 'OBSOLETO');
CREATE TYPE estado_op AS ENUM ('BORRADOR', 'APROBADA', 'LIBERADA_PRODUCCION', 'EN_PROCESO', 'INSPECCION', 'CERRADA', 'RECHAZADA');
CREATE TYPE estado_no_conformidad AS ENUM ('REGISTRADA', 'EN_ANALISIS', 'ACCION_DEFINIDA', 'VERIFICANDO_EFICACIA', 'CERRADA');

-- 2. MÓDULO VENTAS Y CLIENTES (PM-01)
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    razon_social VARCHAR(150) NOT NULL,
    nit VARCHAR(20) UNIQUE NOT NULL,
    contacto_nombre VARCHAR(100),
    contacto_email VARCHAR(100),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE proyectos (
    id SERIAL PRIMARY KEY,
    cliente_id INT NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    codigo_proyecto VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    especificaciones_tecnicas TEXT,
    fecha_compromiso DATE,
    fecha_entrega_real DATE,
    estado estado_proyecto DEFAULT 'BORRADOR',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- RN-VT-001: No se permite pasar a CONFIRMADO sin especificaciones ni fecha comprometida
    CONSTRAINT chk_rn_vt_001 CHECK (
        (estado != 'CONFIRMADO') OR 
        (especificaciones_tecnicas IS NOT NULL AND fecha_compromiso IS NOT NULL)
    )
);

-- 3. MÓDULO DISEÑO E INGENIERÍA (PM-02)
CREATE TABLE planos (
    id SERIAL PRIMARY KEY,
    proyecto_id INT NOT NULL REFERENCES proyectos(id) ON DELETE RESTRICT,
    codigo_plano VARCHAR(50) NOT NULL,
    revision INT NOT NULL DEFAULT 0,
    archivo_url VARCHAR(255) NOT NULL,
    estado estado_plano DEFAULT 'BORRADOR',
    aprobado_por VARCHAR(100),
    fecha_aprobacion TIMESTAMP,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_plano_revision UNIQUE (codigo_plano, revision)
);

CREATE TABLE bom_lista_materiales (
    id SERIAL PRIMARY KEY,
    plano_id INT NOT NULL REFERENCES planos(id) ON DELETE CASCADE,
    codigo_material VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200) NOT NULL,
    cantidad_requerida NUMERIC(10,2) NOT NULL CHECK (cantidad_requerida > 0),
    unidad_medida VARCHAR(20) NOT NULL
);

-- 4. MÓDULO ÓRDENES DE PRODUCCIÓN Y CALIDAD (PM-03 / PC-01)
CREATE TABLE ordenes_produccion (
    id SERIAL PRIMARY KEY,
    codigo_op VARCHAR(50) UNIQUE NOT NULL,
    proyecto_id INT NOT NULL REFERENCES proyectos(id),
    plano_id INT NOT NULL REFERENCES planos(id),
    cantidad_fabricar INT NOT NULL CHECK (cantidad_fabricar > 0),
    estado estado_op DEFAULT 'BORRADOR',
    reserva_stock_100 BOOLEAN DEFAULT FALSE,
    aprobado_por_calidad_id INT,
    liberada_en TIMESTAMP,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- RN-OP-004: Solo se permite LIBERADA_PRODUCCION si el stock reservado está al 100%
    CONSTRAINT chk_rn_op_004 CHECK (
        (estado != 'LIBERADA_PRODUCCION') OR (reserva_stock_100 = TRUE)
    )
);

-- 5. MÓDULO ALMACÉN E INVENTARIOS (PM-04)
CREATE TABLE lotes_material (
    id SERIAL PRIMARY KEY,
    codigo_lote VARCHAR(50) UNIQUE NOT NULL,
    codigo_material VARCHAR(50) NOT NULL,
    stock_disponible NUMERIC(10,2) NOT NULL CHECK (stock_disponible >= 0),
    inspeccionado_calidad BOOLEAN DEFAULT FALSE,
    certificado_calidad_url VARCHAR(255),
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE entregas_material_op (
    id SERIAL PRIMARY KEY,
    op_id INT NOT NULL REFERENCES ordenes_produccion(id),
    lote_id INT NOT NULL REFERENCES lotes_material(id),
    cantidad_entregada NUMERIC(10,2) NOT NULL CHECK (cantidad_entregada > 0),
    entregado_por INT NOT NULL,
    recibido_por_produccion INT NOT NULL,
    fecha_entrega TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. MÓDULO METROLOGÍA E INSPECCIÓN (PM-06)
CREATE TABLE instrumentos_medicion (
    id SERIAL PRIMARY KEY,
    codigo_equipo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    fecha_ultima_calibracion DATE NOT NULL,
    fecha_vencimiento_calibracion DATE NOT NULL,
    estado_disponible BOOLEAN DEFAULT TRUE
);

CREATE TABLE fichas_metrologia (
    id SERIAL PRIMARY KEY,
    op_id INT NOT NULL REFERENCES ordenes_produccion(id),
    instrumento_id INT NOT NULL REFERENCES instrumentos_medicion(id),
    cota_medida NUMERIC(8,3) NOT NULL,
    tolerancia_min NUMERIC(8,3) NOT NULL,
    tolerancia_max NUMERIC(8,3) NOT NULL,
    resultado_conforme BOOLEAN NOT NULL,
    inspector_id INT NOT NULL,
    fecha_inspeccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. MÓDULO NO CONFORMIDADES Y MEJORA CONTINUA (PC-03 / PC-04)
CREATE TABLE no_conformidades (
    id SERIAL PRIMARY KEY,
    codigo_nc VARCHAR(50) UNIQUE NOT NULL,
    op_id INT REFERENCES ordenes_produccion(id),
    origen_proceso VARCHAR(50) NOT NULL,
    descripcion_hallazgo TEXT NOT NULL,
    analisis_causa_5porques TEXT,
    accion_correctiva TEXT,
    eficacia_verificada BOOLEAN DEFAULT FALSE,
    estado estado_no_conformidad DEFAULT 'REGISTRADA',
    cerrado_por_calidad INT,
    fecha_cierre TIMESTAMP,
    -- RN-NC-001: No se permite cerrar una NC sin análisis de causa raíz ni verificación
    CONSTRAINT chk_rn_nc_001 CHECK (
        (estado != 'CERRADA') OR 
        (analisis_causa_5porques IS NOT NULL AND eficacia_verificada = TRUE AND cerrado_por_calidad IS NOT NULL)
    )
);

COMMIT;