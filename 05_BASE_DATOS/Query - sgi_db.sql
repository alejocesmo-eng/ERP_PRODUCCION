-- =============================================================================
-- SISTEMA DE GESTIÓN INTEGRAL (SGI) - ESQUEMA DDL POSTGRESQL (MVP FASE 1)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 1. MÓDULO DE ADMINISTRACIÓN, SEGURIDAD Y PERMISOS (RBAC)
-- -----------------------------------------------------------------------------

CREATE TABLE roles (
    id_rol VARCHAR(20) PRIMARY KEY,
    nombre_rol VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE usuarios (
    id_usuario UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    id_rol VARCHAR(20) NOT NULL REFERENCES roles(id_rol),
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE permisos (
    id_permiso VARCHAR(50) PRIMARY KEY,
    modulo VARCHAR(30) NOT NULL,
    descripcion TEXT
);

CREATE TABLE rol_permisos (
    id_rol VARCHAR(20) REFERENCES roles(id_rol) ON DELETE CASCADE,
    id_permiso VARCHAR(50) REFERENCES permisos(id_permiso) ON DELETE CASCADE,
    PRIMARY KEY (id_rol, id_permiso)
);

-- -----------------------------------------------------------------------------
-- 2. CATÁLOGOS MAESTROS DEL SISTEMA
-- -----------------------------------------------------------------------------

CREATE TABLE clientes (
    id_cliente UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nit_rut VARCHAR(20) NOT NULL UNIQUE,
    razon_social VARCHAR(150) NOT NULL,
    contacto VARCHAR(100),
    email_contacto VARCHAR(100),
    telefono VARCHAR(30)
);

CREATE TABLE empleados (
    id_empleado VARCHAR(20) PRIMARY KEY,
    nombre_completo VARCHAR(100) NOT NULL,
    cargo VARCHAR(50) NOT NULL,
    area VARCHAR(50) NOT NULL,
    id_usuario UUID UNIQUE REFERENCES usuarios(id_usuario)
);

CREATE TABLE maquinas (
    id_maquina VARCHAR(10) PRIMARY KEY, -- Código de 4 dígitos (ej. '0357')
    nombre_maquina VARCHAR(100) NOT NULL,
    tipo_maquina VARCHAR(50),
    foto_url TEXT,
    estado VARCHAR(20) DEFAULT 'OPERATIVA' CHECK (estado IN ('OPERATIVA', 'MANTENIMIENTO', 'FUERA_SERVICIO'))
);

CREATE TABLE articulos_inventario (
    id_articulo VARCHAR(50) PRIMARY KEY, -- Nomenclatura (ej. 'RT-19008-015-0073')
    descripcion TEXT NOT NULL,
    categoria VARCHAR(30) NOT NULL CHECK (categoria IN ('CONSUMIBLE', 'INSERTO', 'MATERIA_PRIMA', 'HERRAMIENTA')),
    stock_actual NUMERIC(10,2) DEFAULT 0.00 CHECK (stock_actual >= 0),
    unidad_medida VARCHAR(20) DEFAULT 'PZA',
    foto_url TEXT
);

-- -----------------------------------------------------------------------------
-- 3. MÓDULO DE VENTAS Y DISEÑO (PROYECTOS Y PLANOS)
-- -----------------------------------------------------------------------------

CREATE TABLE proyectos (
    id_proyecto VARCHAR(20) PRIMARY KEY, -- Código único
    id_cliente UUID NOT NULL REFERENCES clientes(id_cliente),
    nombre_proyecto VARCHAR(150) NOT NULL,
    cantidad_requerida INT NOT NULL CHECK (cantidad_requerida > 0),
    fecha_compromiso DATE NOT NULL,
    confirmacion_cliente_adjunta BOOLEAN DEFAULT FALSE,
    estado VARCHAR(20) DEFAULT 'NUEVO' CHECK (estado IN ('NUEVO', 'EN_DISEÑO', 'APROBADO', 'CANCELADO')),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE planos (
    id_plano UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto VARCHAR(20) NOT NULL REFERENCES proyectos(id_proyecto),
    revision VARCHAR(10) NOT NULL, -- ej. 'Rev.01', 'Rev.02'
    archivo_url TEXT NOT NULL,
    aprobado_diseno BOOLEAN DEFAULT FALSE,
    fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id_proyecto, revision)
);

-- -----------------------------------------------------------------------------
-- 4. MÓDULO DE ORDEN DE PRODUCCIÓN (OP) Y SOLICITUD DE MATERIAL
-- -----------------------------------------------------------------------------

CREATE TABLE ordenes_produccion (
    id_op VARCHAR(20) PRIMARY KEY, -- Código 'OP-YYYY-XXXX'
    id_proyecto VARCHAR(20) NOT NULL REFERENCES proyectos(id_proyecto),
    id_plano_vigente UUID NOT NULL REFERENCES planos(id_plano),
    id_maquina VARCHAR(10) REFERENCES maquinas(id_maquina),
    estado_op VARCHAR(30) DEFAULT 'BORRADOR' CHECK (
        estado_op IN ('BORRADOR', 'LIBERADA', 'EN_FABRICACION', 'PAUSADA', 'PRODUCCION_TERMINADA', 'CERRADA')
    ),
    liberada_en TIMESTAMP,
    cerrada_en TIMESTAMP
);

CREATE TABLE solicitudes_material (
    id_solicitud VARCHAR(20) PRIMARY KEY, -- 'SM-YYYY-XXXX'
    id_op VARCHAR(20) NOT NULL REFERENCES ordenes_produccion(id_op),
    estado_solicitud VARCHAR(20) DEFAULT 'PENDIENTE' CHECK (estado_solicitud IN ('PENDIENTE', 'EN_PREPARACION', 'ENTREGADO_TOTAL', 'ENTREGADO_PARCIAL')),
    fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE retales (
    id_retal VARCHAR(20) PRIMARY KEY, -- 'RET-XXXXXX'
    material_padre VARCHAR(100) NOT NULL,
    largo_mm NUMERIC(8,2) NOT NULL,
    ancho_mm NUMERIC(8,2) NOT NULL,
    espesor_mm NUMERIC(8,2) NOT NULL,
    ubicacion_almacen VARCHAR(50) NOT NULL,
    estado_retal VARCHAR(20) DEFAULT 'DISPONIBLE' CHECK (estado_retal IN ('DISPONIBLE', 'RESERVADO_DISEÑO', 'CONSUMIDO')),
    op_origen VARCHAR(20) REFERENCES ordenes_produccion(id_op)
);

-- -----------------------------------------------------------------------------
-- 5. MÓDULO DE SEGUIMIENTO EN PLANTA (AVANCE Y TIEMPOS)
-- -----------------------------------------------------------------------------

CREATE TABLE avances_produccion (
    id_avance UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_op VARCHAR(20) NOT NULL REFERENCES ordenes_produccion(id_op),
    id_operario VARCHAR(20) NOT NULL REFERENCES empleados(id_empleado),
    piezas_buenas INT NOT NULL DEFAULT 0 CHECK (piezas_buenas >= 0),
    piezas_rechazadas INT NOT NULL DEFAULT 0 CHECK (piezas_rechazadas >= 0),
    motivo_rechazo TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE registro_tiempos_op (
    id_tiempo UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_op VARCHAR(20) NOT NULL REFERENCES ordenes_produccion(id_op),
    id_maquina VARCHAR(10) NOT NULL REFERENCES maquinas(id_maquina),
    id_operario VARCHAR(20) NOT NULL REFERENCES empleados(id_empleado),
    tipo_evento VARCHAR(30) NOT NULL CHECK (tipo_evento IN ('SETUP', 'MAQUINADO', 'PARADA_MANTENIMIENTO', 'PARADA_MATERIAL', 'PAUSA_OPERATIVA')),
    hora_inicio TIMESTAMP NOT NULL,
    hora_fin TIMESTAMP,
    duracion_minutos NUMERIC(10,2) GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (hora_fin - hora_inicio))/60) STORED,
    causa_parada TEXT
);

-- -----------------------------------------------------------------------------
-- 6. MÓDULO DE CALIDAD Y DICTAMEN TÉCNICO (REGLA DE CIERRE)
-- -----------------------------------------------------------------------------

CREATE TABLE inspecciones_calidad (
    id_inspeccion UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_op VARCHAR(20) NOT NULL REFERENCES ordenes_produccion(id_op),
    id_inspector VARCHAR(20) NOT NULL REFERENCES empleados(id_empleado),
    dictamen_calidad VARCHAR(20) NOT NULL CHECK (dictamen_calidad IN ('APROBADA', 'RECHAZADA', 'CORRECCION_REQUERIDA')),
    piezas_inspeccionadas INT NOT NULL,
    piezas_aprobadas INT NOT NULL,
    observaciones TEXT,
    fecha_inspeccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE no_conformidades (
    id_nc VARCHAR(20) PRIMARY KEY, -- 'NC-YYYY-XXXX'
    id_op VARCHAR(20) NOT NULL REFERENCES ordenes_produccion(id_op),
    id_inspeccion UUID REFERENCES inspecciones_calidad(id_inspeccion),
    descripcion_hallazgo TEXT NOT NULL,
    accion_correctiva TEXT,
    estado_nc VARCHAR(20) DEFAULT 'ABIERTA' CHECK (estado_nc IN ('ABIERTA', 'EN_PROCESO', 'CERRADA'))
);

-- -----------------------------------------------------------------------------
-- 7. TRIGGER: REGLA DE BLOQUEO ESTRICTO PARA CERRAR LA OP
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_validar_cierre_op()
RETURNS TRIGGER AS $$
DECLARE
    v_aprobada_calidad BOOLEAN;
BEGIN
    IF NEW.estado_op = 'CERRADA' AND OLD.estado_op <> 'CERRADA' THEN
        SELECT EXISTS (
            SELECT 1 
            FROM inspecciones_calidad 
            WHERE id_op = NEW.id_op 
              AND dictamen_calidad = 'APROBADA'
        ) INTO v_aprobada_calidad;

        IF NOT v_aprobada_calidad THEN
            RAISE EXCEPTION 'NO SE PUEDE CERRAR LA OP (%): Requiere una inspección de calidad con dictamen APROBADA.', NEW.id_op;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bloqueo_cierre_op
BEFORE UPDATE ON ordenes_produccion
FOR EACH ROW
EXECUTE FUNCTION fn_validar_cierre_op();