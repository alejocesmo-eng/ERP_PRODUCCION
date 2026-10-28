-- IMPL-SAP-INV-SEP-003
-- Persistencia de Inventario General (MM-IM), calidad de lotes y kárdex inmutable.

ALTER TABLE articulos_inventario
    ADD COLUMN IF NOT EXISTS tipo_inventario VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
    ADD COLUMN IF NOT EXISTS metodo_valoracion VARCHAR(20) NOT NULL DEFAULT 'PROMEDIO';

ALTER TABLE lotes_material
    ADD COLUMN IF NOT EXISTS numero_colada VARCHAR(50),
    ADD COLUMN IF NOT EXISTS estado_calidad VARCHAR(20);

UPDATE lotes_material
SET estado_calidad = CASE
    WHEN inspeccionado_calidad IS TRUE THEN 'LIBERADO'
    ELSE 'CUARENTENA'
END
WHERE estado_calidad IS NULL;

ALTER TABLE lotes_material
    ALTER COLUMN estado_calidad SET DEFAULT 'CUARENTENA',
    ALTER COLUMN estado_calidad SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_lotes_material_estado_calidad'
    ) THEN
        ALTER TABLE lotes_material
            ADD CONSTRAINT ck_lotes_material_estado_calidad
            CHECK (estado_calidad IN ('CUARENTENA', 'LIBERADO', 'RECHAZADO'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_articulos_inventario_metodo_valoracion'
    ) THEN
        ALTER TABLE articulos_inventario
            ADD CONSTRAINT ck_articulos_inventario_metodo_valoracion
            CHECK (metodo_valoracion IN ('PROMEDIO', 'FIFO'));
    END IF;
END $$;

-- El saldo legado sin trazabilidad no se considera liberado automáticamente.
INSERT INTO lotes_material (
    codigo_lote,
    codigo_material,
    stock_disponible,
    stock_reservado,
    costo_unitario,
    inspeccionado_calidad,
    estado_calidad
)
SELECT
    'LEGACY-' || substr(md5(random()::text || clock_timestamp()::text), 1, 24),
    articulo.codigo_sku,
    articulo.stock_actual - COALESCE(SUM(lote.stock_disponible), 0),
    0,
    articulo.costo_unitario,
    FALSE,
    'CUARENTENA'
FROM articulos_inventario AS articulo
LEFT JOIN lotes_material AS lote
    ON lote.codigo_material = articulo.codigo_sku
GROUP BY articulo.codigo_sku, articulo.stock_actual, articulo.costo_unitario
HAVING articulo.stock_actual > COALESCE(SUM(lote.stock_disponible), 0);

CREATE TABLE IF NOT EXISTS movimientos_inventario (
    id_movimiento UUID PRIMARY KEY,
    id_articulo UUID NOT NULL REFERENCES articulos_inventario(id_articulo),
    id_lote INTEGER NOT NULL REFERENCES lotes_material(id),
    tipo_movimiento VARCHAR(3) NOT NULL,
    cantidad DOUBLE PRECISION NOT NULL,
    costo_unitario NUMERIC(14, 4) NOT NULL,
    valor_total NUMERIC(14, 4) NOT NULL,
    saldo_cantidad DOUBLE PRECISION NOT NULL,
    referencia_tipo VARCHAR(30) NOT NULL,
    referencia_id VARCHAR(100) NOT NULL,
    documento_externo VARCHAR(100),
    documento_url VARCHAR(255),
    proveedor VARCHAR(150),
    codigo_op VARCHAR(50),
    destino VARCHAR(100),
    registrado_por VARCHAR(150) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_movimientos_inventario_tipo
        CHECK (tipo_movimiento IN ('101', '201', '261', '311', '701', '702')),
    CONSTRAINT ck_movimientos_inventario_valores
        CHECK (cantidad > 0 AND costo_unitario >= 0 AND valor_total >= 0 AND saldo_cantidad >= 0)
);

CREATE INDEX IF NOT EXISTS ix_movimientos_inventario_articulo
    ON movimientos_inventario (id_articulo);
CREATE INDEX IF NOT EXISTS ix_movimientos_inventario_lote
    ON movimientos_inventario (id_lote);
CREATE INDEX IF NOT EXISTS ix_movimientos_inventario_fecha
    ON movimientos_inventario (creado_en DESC);
CREATE INDEX IF NOT EXISTS ix_movimientos_inventario_referencia
    ON movimientos_inventario (referencia_tipo, referencia_id);

CREATE TABLE IF NOT EXISTS auditoria_calidad_lotes (
    id_registro UUID PRIMARY KEY,
    id_lote INTEGER NOT NULL REFERENCES lotes_material(id),
    estado_anterior VARCHAR(20),
    estado_nuevo VARCHAR(20) NOT NULL,
    motivo TEXT NOT NULL,
    registrado_por VARCHAR(150) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_auditoria_calidad_lotes_estado
        CHECK (estado_nuevo IN ('CUARENTENA', 'LIBERADO', 'RECHAZADO'))
);

CREATE INDEX IF NOT EXISTS ix_auditoria_calidad_lotes_lote
    ON auditoria_calidad_lotes (id_lote, creado_en DESC);

CREATE OR REPLACE FUNCTION rechazar_edicion_kardex_inventario()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Los movimientos del kárdex son inmutables.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_movimientos_inventario_inmutables ON movimientos_inventario;
CREATE TRIGGER trg_movimientos_inventario_inmutables
    BEFORE UPDATE OR DELETE ON movimientos_inventario
    FOR EACH ROW EXECUTE FUNCTION rechazar_edicion_kardex_inventario();

DROP TRIGGER IF EXISTS trg_auditoria_calidad_lotes_inmutable ON auditoria_calidad_lotes;
CREATE TRIGGER trg_auditoria_calidad_lotes_inmutable
    BEFORE UPDATE OR DELETE ON auditoria_calidad_lotes
    FOR EACH ROW EXECUTE FUNCTION rechazar_edicion_kardex_inventario();
