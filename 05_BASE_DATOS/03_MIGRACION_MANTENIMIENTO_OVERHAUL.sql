-- =============================================================================
-- MIGRACIÓN BASE DE DATOS: MÓDULO DE MANTENIMIENTO Y OVERHAUL (SGI - ISO 9001:2026)
-- Conecta con la base de datos existente sgi_db
-- =============================================================================

-- 1. CABECERA DE MANTENIMIENTOS / OVERHAUL DE MÁQUINAS
CREATE TABLE IF NOT EXISTS mantenimientos_maquinas (
    id_mantenimiento SERIAL PRIMARY KEY,
    id_proyecto INT,
    codigo_mantenimiento VARCHAR(30) UNIQUE NOT NULL,
    nombre_maquina VARCHAR(150) NOT NULL,
    marca_modelo VARCHAR(100),
    serie_maquina VARCHAR(50),
    fase_mantenimiento VARCHAR(30) DEFAULT 'LAVADO_DESARME',
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_estimada_entrega DATE,
    observaciones_ingreso TEXT
);

-- 2. LEVANTAMIENTO TÉCNICO DE PIEZAS (10 A 300+ ÍTEMS)
CREATE TABLE IF NOT EXISTS mantenimientos_piezas_det (
    id_pieza_mant SERIAL PRIMARY KEY,
    id_mantenimiento INT REFERENCES mantenimientos_maquinas(id_mantenimiento) ON DELETE CASCADE,
    posicion_item INT NOT NULL,
    codigo_pieza_plano VARCHAR(50) NOT NULL,
    revision VARCHAR(10) DEFAULT 'REV-01',
    descripcion_pieza VARCHAR(200) NOT NULL,
    accion_requerida VARCHAR(30) NOT NULL,
    cantidad_requerida INT NOT NULL DEFAULT 1,
    material_especificado VARCHAR(100),
    autorizado_cliente BOOLEAN DEFAULT FALSE,
    precio_unitario_cotizado NUMERIC(12,2) DEFAULT 0.00,
    id_sublote_mes VARCHAR(50),
    estado_fabricacion VARCHAR(30) DEFAULT 'PENDIENTE_APROBACION'
);

-- 3. HISTORIAL DE SERVICIOS EN PLANTA
CREATE TABLE IF NOT EXISTS mantenimientos_servicios_planta (
    id_servicio SERIAL PRIMARY KEY,
    id_mantenimiento INT REFERENCES mantenimientos_maquinas(id_mantenimiento) ON DELETE CASCADE,
    tipo_servicio VARCHAR(30) NOT NULL,
    operario_responsable VARCHAR(100) NOT NULL,
    horas_invertidas NUMERIC(6,2) DEFAULT 0.0,
    novedades_tecnicas TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ÍNDICES DE RENDIMIENTO
CREATE INDEX IF NOT EXISTS idx_mantenimiento_fase ON mantenimientos_maquinas(fase_mantenimiento);
CREATE INDEX IF NOT EXISTS idx_piezas_mantenimiento ON mantenimientos_piezas_det(id_mantenimiento);
CREATE INDEX IF NOT EXISTS idx_piezas_autorizadas ON mantenimientos_piezas_det(autorizado_cliente);

-- VISTA MONITOR DE KITS
CREATE OR REPLACE VIEW vista_monitor_kits_mantenimiento AS
SELECT 
    m.id_mantenimiento,
    m.codigo_mantenimiento,
    m.nombre_maquina,
    m.fase_mantenimiento,
    COUNT(pd.id_pieza_mant) FILTER (WHERE pd.autorizado_cliente = TRUE) AS total_piezas_autorizadas,
    COUNT(pd.id_pieza_mant) FILTER (WHERE pd.autorizado_cliente = TRUE AND pd.estado_fabricacion = 'LISTO_EN_KIT') AS piezas_terminadas_ok,
    ROUND(
        (COUNT(pd.id_pieza_mant) FILTER (WHERE pd.autorizado_cliente = TRUE AND pd.estado_fabricacion = 'LISTO_EN_KIT')::NUMERIC / 
        NULLIF(COUNT(pd.id_pieza_mant) FILTER (WHERE pd.autorizado_cliente = TRUE), 0)) * 100, 2
    ) AS porcentaje_kit_listo
FROM mantenimientos_maquinas m
LEFT JOIN mantenimientos_piezas_det pd ON m.id_mantenimiento = pd.id_mantenimiento
GROUP BY m.id_mantenimiento, m.codigo_mantenimiento, m.nombre_maquina, m.fase_mantenimiento;