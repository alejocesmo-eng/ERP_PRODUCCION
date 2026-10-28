-- IMPL-DATOS-MAESTROS-001
-- Datos maestros unificados, personal vinculado a usuarios y estructura financiera.

CREATE TABLE IF NOT EXISTS socios_negocio (
    id_socio UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nit_cedula VARCHAR(30) NOT NULL UNIQUE,
    razon_social VARCHAR(200) NOT NULL,
    es_cliente BOOLEAN NOT NULL DEFAULT FALSE,
    es_proveedor BOOLEAN NOT NULL DEFAULT FALSE,
    direccion VARCHAR(255),
    telefono VARCHAR(50),
    email VARCHAR(150),
    condiciones_pago_dias INTEGER NOT NULL DEFAULT 30,
    cuenta_contable_por_cobrar VARCHAR(100),
    cuenta_contable_por_pagar VARCHAR(100),
    estado_activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_socios_negocio_tipo CHECK (es_cliente OR es_proveedor),
    CONSTRAINT ck_socios_negocio_condiciones_pago CHECK (
        condiciones_pago_dias BETWEEN 0 AND 365
    )
);

CREATE TABLE IF NOT EXISTS trabajadores_usuarios (
    id_trabajador UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cedula VARCHAR(30) NOT NULL UNIQUE,
    nombre_completo VARCHAR(150) NOT NULL,
    area VARCHAR(20) NOT NULL,
    cargo VARCHAR(100) NOT NULL,
    tarifa_hora_mano_obra NUMERIC(14, 4) NOT NULL DEFAULT 0,
    id_usuario_sistema UUID UNIQUE REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT ck_trabajadores_usuarios_area_trabajador_enum CHECK (
        area IN ('VENTAS', 'DISENO', 'ALMACEN', 'PRODUCCION', 'CALIDAD', 'ADMINISTRACION')
    ),
    CONSTRAINT ck_trabajadores_usuarios_tarifa CHECK (tarifa_hora_mano_obra >= 0)
);

CREATE TABLE IF NOT EXISTS estructura_financiera (
    id_elemento UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo VARCHAR(20) NOT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    cuenta_padre VARCHAR(50) REFERENCES estructura_financiera(codigo),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_estructura_financiera_tipo CHECK (
        tipo IN ('CUENTA_CONTABLE', 'CENTRO_COSTO', 'UNIDAD_NEGOCIO')
    )
);

CREATE TABLE IF NOT EXISTS unidades_medida (
    id_unidad UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    simbolo VARCHAR(20) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categorias_inventario (
    id_categoria UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    icono VARCHAR(10) DEFAULT '📦',
    descripcion TEXT,
    es_personalizada BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO socios_negocio (
    id_socio,
    nit_cedula,
    razon_social,
    es_cliente,
    es_proveedor,
    telefono,
    email,
    creado_en,
    actualizado_en
)
SELECT
    gen_random_uuid(),
    cliente.nit_rut,
    cliente.razon_social,
    TRUE,
    FALSE,
    cliente.telefono,
    cliente.email_contacto,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM clientes AS cliente
WHERE cliente.nit_rut IS NOT NULL
ON CONFLICT (nit_cedula) DO NOTHING;

INSERT INTO unidades_medida (id_unidad, codigo, nombre, simbolo, activo, creado_en)
VALUES
    (gen_random_uuid(), 'KG', 'Kilogramo', 'kg', TRUE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'M', 'Metro', 'm', TRUE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'MM', 'Milímetro', 'mm', TRUE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'UND', 'Unidad', 'und', TRUE, CURRENT_TIMESTAMP)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO categorias_inventario (
    id_categoria,
    codigo,
    nombre,
    icono,
    descripcion,
    es_personalizada,
    creado_en
)
VALUES
    (gen_random_uuid(), 'MATERIA_PRIMA', 'Materia Prima Directa', '📦', 'Materias primas para fabricación.', FALSE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'HERRAMENTAL', 'Herramental CNC', '🔧', 'Herramientas y elementos de sujeción CNC.', FALSE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'CONSUMIBLE', 'Consumibles', '🛠', 'Consumibles de planta y producción.', FALSE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'EPP', 'Equipos de Protección', '🥽', 'Elementos de protección personal.', FALSE, CURRENT_TIMESTAMP),
    (gen_random_uuid(), 'REPUESTO', 'Repuestos', '⚙', 'Repuestos de máquinas y equipos.', FALSE, CURRENT_TIMESTAMP)
ON CONFLICT (codigo) DO NOTHING;
