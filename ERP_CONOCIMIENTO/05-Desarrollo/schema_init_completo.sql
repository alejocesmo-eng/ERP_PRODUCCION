-- =============================================================================
-- ESQUEMA CANÓNICO INTEGRAL — SISTEMA DE GESTIÓN INTEGRAL (SGI - ISO 9001:2026)
-- ARCHIVO: ERP_CONOCIMIENTO/05-Desarrollo/schema_init_completo.sql
-- Homologación unificada: UUID transaccional, SERIAL operativo y claves naturales.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. TIPOS ENUMERADOS DEL SISTEMA
-- -----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE estado_proyecto AS ENUM ('BORRADOR', 'CONFIRMADO', 'EN_DISENO', 'FINALIZADO', 'CANCELADO');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE estado_plano AS ENUM ('BORRADOR', 'EN_REVISION', 'APROBADO', 'OBSOLETO');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE estado_op AS ENUM (
        'BORRADOR', 'EN_REVISION_CALIDAD', 'APROBADA', 'PENDIENTE_MATERIAL', 
        'LIBERADA_PRODUCCION', 'EN_PRODUCCION', 'EN_INSPECCION', 'CERRADA', 'CANCELADA'
    );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE estado_no_conformidad AS ENUM (
        'ABIERTA', 'REGISTRADA', 'EN_ANALISIS', 'ACCION_CORRECTIVA', 
        'ACCION_DEFINIDA', 'VERIFICANDO_EFICACIA', 'CERRADA'
    );
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- -----------------------------------------------------------------------------
-- 2. SEGURIDAD Y CONTROL DE ACCESO (RBAC)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id_rol VARCHAR(50) PRIMARY KEY,
    nombre_rol VARCHAR(100) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS permisos (
    id_permiso VARCHAR(100) PRIMARY KEY,
    modulo VARCHAR(50) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    id_rol VARCHAR(50) REFERENCES roles(id_rol),
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 3. CATÁLOGOS MAESTROS Y RECURSOS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nit_rut VARCHAR(50) UNIQUE NOT NULL,
    razon_social VARCHAR(150) NOT NULL,
    contacto VARCHAR(100),
    email_contacto VARCHAR(100),
    telefono VARCHAR(50),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maquinas (
    id_maquina VARCHAR(50) PRIMARY KEY,
    nombre_maquina VARCHAR(100) NOT NULL,
    tipo_maquina VARCHAR(50),
    estado VARCHAR(50) DEFAULT 'OPERATIVA'
);

CREATE TABLE IF NOT EXISTS empleados (
    id_empleado VARCHAR(50) PRIMARY KEY,
    nombre_completo VARCHAR(150) NOT NULL,
    cargo VARCHAR(100),
    area VARCHAR(100)
);

-- -----------------------------------------------------------------------------
-- 4. MÓDULO COMERCIAL Y VENTAS (PM-01)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proyectos (
    id_proyecto UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_cliente UUID REFERENCES clientes(id_cliente),
    numero_pedido VARCHAR(50) NOT NULL,
    codigo_proyecto VARCHAR(50) NOT NULL,
    cliente_nombre VARCHAR(150) NOT NULL,
    contacto_nombre VARCHAR(150),
    contacto_telefono VARCHAR(50),
    contacto_email VARCHAR(100),
    ubicacion_cliente VARCHAR(150),
    cantidad INTEGER DEFAULT 1,
    detalle_producto TEXT,
    requisitos_cliente TEXT NOT NULL,
    fecha_compromiso DATE,
    fecha_entrega_real DATE,
    confirmado BOOLEAN DEFAULT FALSE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pedido_detalles (
    detalle_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pedido_id UUID NOT NULL REFERENCES proyectos(id_proyecto) ON DELETE CASCADE,
    codigo_producto VARCHAR(50),
    descripcion VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) DEFAULT 'PIEZA',
    cantidad_solicitada INTEGER NOT NULL DEFAULT 1,
    unidad VARCHAR(20) DEFAULT 'UND',
    cantidad_asignada INTEGER DEFAULT 0,
    cantidad_pendiente INTEGER DEFAULT 1,
    fecha_requerida DATE,
    prioridad VARCHAR(20) DEFAULT 'MEDIA',
    observaciones TEXT,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 5. MÓDULO MANTENIMIENTO & OVERHAUL
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mantenimientos_maquinas (
    id_mantenimiento SERIAL PRIMARY KEY,
    codigo_mantenimiento VARCHAR(50) UNIQUE NOT NULL,
    cliente_nombre VARCHAR(150) NOT NULL,
    codigo_op VARCHAR(50) NOT NULL,
    nombre_maquina VARCHAR(150) NOT NULL,
    marca_modelo VARCHAR(150),
    serie_maquina VARCHAR(100),
    observaciones_ingreso TEXT,
    fase_mantenimiento VARCHAR(50) DEFAULT 'LAVADO_DESARME' NOT NULL,
    confirmado BOOLEAN DEFAULT FALSE NOT NULL,
    total_piezas_autorizadas INTEGER DEFAULT 0,
    piezas_terminadas_ok INTEGER DEFAULT 0,
    porcentaje_kit_listo DOUBLE PRECISION DEFAULT 0.0,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mantenimientos_piezas_det (
    id_pieza_det SERIAL PRIMARY KEY,
    id_mantenimiento INTEGER NOT NULL REFERENCES mantenimientos_maquinas(id_mantenimiento) ON DELETE CASCADE,
    codigo_item VARCHAR(50) NOT NULL,
    descripcion_pieza VARCHAR(200) NOT NULL,
    cantidad INTEGER DEFAULT 1,
    accion_tecnica VARCHAR(50) NOT NULL,
    estado_pieza VARCHAR(50) DEFAULT 'DIAGNOSTICO',
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 6. MÓDULO DISEÑO E INGENIERÍA (PM-02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS planos (
    id_plano UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto UUID NOT NULL REFERENCES proyectos(id_proyecto) ON DELETE CASCADE,
    id_mantenimiento INTEGER REFERENCES mantenimientos_maquinas(id_mantenimiento) ON DELETE SET NULL,
    codigo_op VARCHAR(50) NOT NULL DEFAULT '4007256',
    codigo_plano VARCHAR(50) NOT NULL,
    revision VARCHAR(10) NOT NULL DEFAULT 'REV-01',
    dibujante_asignado VARCHAR(150) DEFAULT 'Carlos Ruiz',
    unidad_planta VARCHAR(100) DEFAULT 'Mecanizados',
    estado_diseno VARCHAR(50) DEFAULT 'PLANIFICADA',
    causa_espera TEXT,
    material_requerido TEXT,
    insumos_opcionales TEXT,
    tiempo_estimado_valor INTEGER DEFAULT 4,
    tiempo_estimado_unidad VARCHAR(20) DEFAULT 'HORAS',
    dias_estimados_diseno INTEGER DEFAULT 2,
    dias_espera_planificacion INTEGER DEFAULT 0,
    fecha_inicio_programada DATE,
    fecha_entrega_cliente DATE,
    fecha_entrega_produccion DATE,
    archivo_url VARCHAR(255),
    estado VARCHAR(50) DEFAULT 'BORRADOR',
    aprobado_por VARCHAR(100),
    fecha_aprobacion TIMESTAMP WITH TIME ZONE,
    creado_por UUID REFERENCES usuarios(id_usuario),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ot_detalles (
    ot_detalle_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detalle_pedido_id UUID NOT NULL REFERENCES pedido_detalles(detalle_id) ON DELETE CASCADE,
    ot_id UUID NOT NULL REFERENCES planos(id_plano) ON DELETE CASCADE,
    cantidad_asignada INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bom_lista_materiales (
    id SERIAL PRIMARY KEY,
    plano_id UUID NOT NULL REFERENCES planos(id_plano) ON DELETE CASCADE,
    codigo_material VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200) NOT NULL,
    cantidad_requerida DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    unidad_medida VARCHAR(20) NOT NULL DEFAULT 'UND'
);

-- -----------------------------------------------------------------------------
-- 7. MÓDULO ÓRDENES DE PRODUCCIÓN (PM-03)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ordenes_produccion (
    id_op UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto UUID NOT NULL REFERENCES proyectos(id_proyecto) ON DELETE CASCADE,
    id_plano UUID REFERENCES planos(id_plano),
    id_mantenimiento INTEGER REFERENCES mantenimientos_maquinas(id_mantenimiento) ON DELETE SET NULL,
    codigo_op VARCHAR(50) UNIQUE NOT NULL,
    cantidad_fabricar INTEGER DEFAULT 1 NOT NULL,
    estado VARCHAR(50) DEFAULT 'BORRADOR',
    reserva_stock_100 BOOLEAN DEFAULT FALSE,
    aprobado_por_calidad_id UUID REFERENCES usuarios(id_usuario),
    liberada_en TIMESTAMP WITH TIME ZONE,
    observaciones TEXT,
    porcentaje_avance DOUBLE PRECISION DEFAULT 0.0,
    estado_calidad VARCHAR(30),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 8. MÓDULO ALMACÉN, INVENTARIOS Y COMPRAS (PM-04)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articulos_inventario (
    id_articulo UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_sku VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(50),
    unidad_medida VARCHAR(20) DEFAULT 'UND',
    stock_actual DOUBLE PRECISION DEFAULT 0.0,
    stock_minimo DOUBLE PRECISION DEFAULT 0.0,
    ubicacion VARCHAR(100),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lotes_material (
    id SERIAL PRIMARY KEY,
    codigo_lote VARCHAR(50) UNIQUE NOT NULL,
    codigo_material VARCHAR(50) NOT NULL,
    stock_disponible DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    inspeccionado_calidad BOOLEAN DEFAULT FALSE,
    certificado_calidad_url VARCHAR(255),
    fecha_ingreso TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entregas_material_op (
    id SERIAL PRIMARY KEY,
    op_id UUID NOT NULL REFERENCES ordenes_produccion(id_op) ON DELETE CASCADE,
    lote_id INTEGER NOT NULL REFERENCES lotes_material(id),
    cantidad_entregada DOUBLE PRECISION NOT NULL,
    entregado_por UUID NOT NULL REFERENCES usuarios(id_usuario),
    recibido_por_produccion UUID NOT NULL REFERENCES usuarios(id_usuario),
    fecha_entrega TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solicitudes_compra (
    id_solicitud UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    numero_solicitud VARCHAR(50) NOT NULL,
    codigo_op VARCHAR(50),
    codigo_plano VARCHAR(50),
    numero_pedido VARCHAR(50),
    nombre_item VARCHAR(150) NOT NULL,
    codigo_sku VARCHAR(50),
    categoria VARCHAR(50) DEFAULT 'MATERIA_PRIMA',
    cantidad_solicitada DOUBLE PRECISION DEFAULT 1.0,
    unidad_medida VARCHAR(20) DEFAULT 'UND',
    estado VARCHAR(50) DEFAULT 'PENDIENTE',
    fecha_solicitud TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    proveedor_sugerido VARCHAR(150),
    observaciones TEXT,
    id_proyecto UUID REFERENCES proyectos(id_proyecto) ON DELETE SET NULL,
    id_plano UUID REFERENCES planos(id_plano) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS entradas_mercancia (
    id_entrada UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    numero_factura_remision VARCHAR(100) NOT NULL,
    proveedor VARCHAR(150) NOT NULL,
    fecha_recepcion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    recibido_por UUID REFERENCES usuarios(id_usuario)
);

CREATE TABLE IF NOT EXISTS ajustes_inventario (
    id_ajuste UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_articulo UUID NOT NULL REFERENCES articulos_inventario(id_articulo),
    tipo_ajuste VARCHAR(20) NOT NULL,
    cantidad DOUBLE PRECISION NOT NULL,
    motivo TEXT NOT NULL,
    fecha_ajuste TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 9. MÓDULO METROLOGÍA, CALIDAD Y RNC (PM-06 / PC-01 / PC-03)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instrumentos_medicion (
    id SERIAL PRIMARY KEY,
    codigo_equipo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    fecha_ultima_calibracion DATE NOT NULL,
    fecha_vencimiento_calibracion DATE NOT NULL,
    estado_disponible BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS fichas_metrologia (
    id SERIAL PRIMARY KEY,
    op_id UUID NOT NULL REFERENCES ordenes_produccion(id_op) ON DELETE CASCADE,
    instrumento_id INTEGER NOT NULL REFERENCES instrumentos_medicion(id),
    cota_medida DOUBLE PRECISION NOT NULL,
    tolerancia_min DOUBLE PRECISION NOT NULL,
    tolerancia_max DOUBLE PRECISION NOT NULL,
    resultado_conforme BOOLEAN NOT NULL,
    inspector_id UUID NOT NULL REFERENCES usuarios(id_usuario),
    fecha_inspeccion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS no_conformidades (
    id_nc UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_nc VARCHAR(50) UNIQUE NOT NULL,
    id_op UUID REFERENCES ordenes_produccion(id_op),
    descripcion TEXT NOT NULL,
    origen VARCHAR(100) DEFAULT 'INSPECCION_PROCESO',
    gravedad VARCHAR(50) DEFAULT 'MENOR',
    estado VARCHAR(50) DEFAULT 'REGISTRADA',
    accion_correctiva TEXT,
    analisis_causa_5porques TEXT,
    eficacia_verificada BOOLEAN DEFAULT FALSE,
    cerrado_por_calidad UUID REFERENCES usuarios(id_usuario),
    fecha_cierre TIMESTAMP WITH TIME ZONE,
    reportado_por UUID REFERENCES usuarios(id_usuario),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inspecciones_calidad (
    id_inspeccion UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_op VARCHAR(50) NOT NULL,
    codigo_plano VARCHAR(50) NOT NULL,
    inspector_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    inspector_nombre VARCHAR(150) NOT NULL,
    resultado_inspeccion VARCHAR(30) NOT NULL,
    requiere_tratamiento BOOLEAN DEFAULT FALSE,
    descripcion_tratamiento TEXT,
    piezas_enviadas_tratamiento INTEGER DEFAULT 0,
    proveedor_tratamiento_email VARCHAR(150),
    registros_fotograficos JSONB DEFAULT '[]'::jsonb,
    observaciones_inspector TEXT,
    notificado_jefe_produccion BOOLEAN DEFAULT FALSE,
    fecha_inspeccion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 10. MÓDULO PRODUCCIÓN MES (TABLERO LÍDER Y TABLETS OPERARIO)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operaciones_ot (
    id_operacion UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_plano UUID NOT NULL REFERENCES planos(id_plano),
    codigo_op VARCHAR(50) NOT NULL,
    codigo_plano VARCHAR(50) NOT NULL,
    secuencia_paso INTEGER NOT NULL DEFAULT 1,
    unidad_planta VARCHAR(50) DEFAULT 'Mecanizados',
    nombre_proceso VARCHAR(100) NOT NULL,
    cantidad_total_orden INTEGER NOT NULL DEFAULT 1,
    cantidad_acumulada_ok INTEGER DEFAULT 0,
    estado_operacion VARCHAR(50) DEFAULT 'PENDIENTE',
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sublotes_operacion (
    id_sublote UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_operacion UUID NOT NULL REFERENCES operaciones_ot(id_operacion),
    numero_sublote VARCHAR(20) DEFAULT 'LOTE-1',
    cantidad_asignada INTEGER NOT NULL DEFAULT 1,
    operario_id VARCHAR(100),
    operario_nombre VARCHAR(150),
    maquina_codigo VARCHAR(50),
    estado_sublote VARCHAR(50) DEFAULT 'EN_COLA'
);

CREATE TABLE IF NOT EXISTS registros_tiempo_operario (
    id_registro UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_sublote UUID NOT NULL REFERENCES sublotes_operacion(id_sublote),
    operario_id VARCHAR(100) NOT NULL,
    maquina_codigo VARCHAR(50) NOT NULL,
    fecha_apertura_setup TIMESTAMP WITH TIME ZONE,
    fecha_inicio_produccion TIMESTAMP WITH TIME ZONE,
    fecha_fin_operacion TIMESTAMP WITH TIME ZONE,
    tiempo_setup_segundos INTEGER DEFAULT 0,
    tiempo_produccion_segundos INTEGER DEFAULT 0,
    piezas_conformes_ok INTEGER NOT NULL DEFAULT 0,
    piezas_defectuosas_scrap INTEGER NOT NULL DEFAULT 0,
    es_entrega_parcial INTEGER DEFAULT 0,
    comentarios_operario TEXT,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notificaciones_lider (
    id_notificacion UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_sublote UUID REFERENCES sublotes_operacion(id_sublote),
    unidad_planta VARCHAR(50) NOT NULL,
    tipo_notificacion VARCHAR(50) NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    mensaje TEXT NOT NULL,
    codigo_op VARCHAR(50) NOT NULL,
    codigo_plano VARCHAR(50) NOT NULL,
    operario_nombre VARCHAR(150) NOT NULL,
    maquina_codigo VARCHAR(50) NOT NULL,
    piezas_reportadas INTEGER,
    leida INTEGER DEFAULT 0,
    atendida INTEGER DEFAULT 0,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMIT;

