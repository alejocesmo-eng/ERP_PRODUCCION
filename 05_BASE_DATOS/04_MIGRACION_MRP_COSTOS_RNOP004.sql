-- IMPL-SAP-SYNC-001
-- Extiende el esquema SGI para MRP, gate RN-OP-004 y costos reales por OP.

ALTER TABLE proyectos
    ADD COLUMN IF NOT EXISTS cotizacion_total NUMERIC(14, 2);

ALTER TABLE bom_lista_materiales
    ADD COLUMN IF NOT EXISTS estado_abastecimiento VARCHAR(30) NOT NULL DEFAULT 'SIN_SOLICITAR';

ALTER TABLE articulos_inventario
    ADD COLUMN IF NOT EXISTS stock_reservado DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_unitario NUMERIC(14, 4) NOT NULL DEFAULT 0;

ALTER TABLE lotes_material
    ADD COLUMN IF NOT EXISTS stock_reservado DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_unitario NUMERIC(14, 4) NOT NULL DEFAULT 0;

ALTER TABLE solicitudes_compra
    ADD COLUMN IF NOT EXISTS estado_bom VARCHAR(30) NOT NULL DEFAULT 'SOLICITADO';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'estadoopenum') THEN
        ALTER TYPE estadoopenum ADD VALUE IF NOT EXISTS 'LISTA_PARA_LIBERAR';
        ALTER TYPE estadoopenum ADD VALUE IF NOT EXISTS 'LIBERADA';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS retales_sobrantes (
    id_retal UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_retal VARCHAR(50) UNIQUE NOT NULL,
    codigo_material VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200),
    dimensiones VARCHAR(200),
    unidad_medida VARCHAR(20) NOT NULL DEFAULT 'UND',
    cantidad_disponible DOUBLE PRECISION NOT NULL DEFAULT 0,
    cantidad_reservada DOUBLE PRECISION NOT NULL DEFAULT 0,
    reutilizable BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_retales_cantidad_no_negativa CHECK (cantidad_disponible >= 0 AND cantidad_reservada >= 0)
);
CREATE INDEX IF NOT EXISTS ix_retales_codigo_material ON retales_sobrantes (codigo_material);

CREATE TABLE IF NOT EXISTS ejecuciones_mrp (
    id_ejecucion UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ejecutado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ejecutado_por VARCHAR(100),
    estado VARCHAR(30) NOT NULL DEFAULT 'COMPLETADA'
);

CREATE TABLE IF NOT EXISTS requisiciones_mrp (
    id_requisicion UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_ejecucion UUID NOT NULL REFERENCES ejecuciones_mrp(id_ejecucion) ON DELETE CASCADE,
    codigo_material VARCHAR(50) NOT NULL,
    especificacion VARCHAR(200) NOT NULL,
    unidad_medida VARCHAR(20) NOT NULL,
    demanda_bruta DOUBLE PRECISION NOT NULL,
    stock_libre DOUBLE PRECISION NOT NULL,
    retales_disponibles DOUBLE PRECISION NOT NULL,
    compras_en_transito DOUBLE PRECISION NOT NULL,
    stock_reservado DOUBLE PRECISION NOT NULL,
    requerimiento_neto DOUBLE PRECISION NOT NULL,
    numero_solicitud VARCHAR(50),
    estado VARCHAR(30) NOT NULL DEFAULT 'SOLICITADO',
    solicitud_id UUID REFERENCES solicitudes_compra(id_solicitud) ON DELETE SET NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_requisicion_mrp_cantidades CHECK (
        demanda_bruta >= 0 AND stock_libre >= 0 AND retales_disponibles >= 0
        AND compras_en_transito >= 0 AND stock_reservado >= 0 AND requerimiento_neto >= 0
    )
);
CREATE INDEX IF NOT EXISTS ix_requisiciones_mrp_material ON requisiciones_mrp (codigo_material, creado_en);

CREATE TABLE IF NOT EXISTS trazabilidad_requisicion_mrp (
    id BIGSERIAL PRIMARY KEY,
    requisicion_id UUID NOT NULL REFERENCES requisiciones_mrp(id_requisicion) ON DELETE CASCADE,
    codigo_op VARCHAR(50) NOT NULL,
    codigo_plano VARCHAR(50) NOT NULL,
    cantidad_demanda DOUBLE PRECISION NOT NULL,
    CONSTRAINT ck_trazabilidad_mrp_cantidad CHECK (cantidad_demanda > 0),
    CONSTRAINT uq_trazabilidad_mrp_demanda UNIQUE (requisicion_id, codigo_op, codigo_plano)
);

CREATE TABLE IF NOT EXISTS centros_trabajo (
    id_centro UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_centro VARCHAR(50) UNIQUE NOT NULL,
    tarifa_hora_mecanizado NUMERIC(14, 4) NOT NULL DEFAULT 0,
    tarifa_hora_setup NUMERIC(14, 4) NOT NULL DEFAULT 0,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_centros_trabajo_tarifas CHECK (tarifa_hora_mecanizado >= 0 AND tarifa_hora_setup >= 0)
);

CREATE TABLE IF NOT EXISTS consumos_material_op (
    id_consumo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    op_id UUID NOT NULL REFERENCES ordenes_produccion(id_op) ON DELETE CASCADE,
    codigo_material VARCHAR(50) NOT NULL,
    descripcion_material VARCHAR(200) NOT NULL,
    cantidad DOUBLE PRECISION NOT NULL,
    unidad_medida VARCHAR(20) NOT NULL,
    costo_unitario NUMERIC(14, 4) NOT NULL,
    fuente VARCHAR(30) NOT NULL DEFAULT 'KARDEX',
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_consumo_material_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_consumo_material_costo CHECK (costo_unitario >= 0)
);
CREATE INDEX IF NOT EXISTS ix_consumos_material_op_op_id ON consumos_material_op (op_id);

CREATE TABLE IF NOT EXISTS servicios_terceros_op (
    id_servicio UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    op_id UUID NOT NULL REFERENCES ordenes_produccion(id_op) ON DELETE CASCADE,
    proveedor VARCHAR(150) NOT NULL,
    descripcion VARCHAR(200) NOT NULL,
    numero_factura VARCHAR(100) NOT NULL,
    costo NUMERIC(14, 2) NOT NULL,
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_servicio_terceros_costo CHECK (costo >= 0)
);
CREATE INDEX IF NOT EXISTS ix_servicios_terceros_op_op_id ON servicios_terceros_op (op_id);
