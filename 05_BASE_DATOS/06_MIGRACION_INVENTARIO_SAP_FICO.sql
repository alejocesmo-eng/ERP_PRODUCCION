-- IMPL-SAP-INV-ENTERPRISE-001
-- Maestro SAP MM, estructura de centros/almacenes y documentos FI/CO.

CREATE TABLE IF NOT EXISTS centros_almacen (
    id_centro UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_centro VARCHAR(50) NOT NULL UNIQUE,
    nombre_centro VARCHAR(150) NOT NULL,
    almacenes JSONB NOT NULL DEFAULT '[]'::jsonb,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_centros_almacen_lista CHECK (jsonb_typeof(almacenes) = 'array')
);

INSERT INTO centros_almacen (
    id_centro,
    codigo_centro,
    nombre_centro,
    almacenes,
    activo,
    creado_en
)
VALUES (
    gen_random_uuid(),
    'CENTRO-01-FUNZA',
    'Centro Funza',
    '["BOD-MP-01", "BOD-HERR-02", "BOD-CUARENTENA-QM", "BOD-RETALES"]'::jsonb,
    TRUE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (codigo_centro) DO NOTHING;

ALTER TABLE lotes_material
    ADD COLUMN IF NOT EXISTS codigo_centro VARCHAR(50),
    ADD COLUMN IF NOT EXISTS almacen_fisico VARCHAR(50);

CREATE TABLE IF NOT EXISTS catalogo_materiales_sap (
    id_material UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_articulo UUID NOT NULL UNIQUE REFERENCES articulos_inventario(id_articulo) ON DELETE CASCADE,
    sku_codigo VARCHAR(50) NOT NULL UNIQUE REFERENCES articulos_inventario(codigo_sku),
    descripcion_tecnica VARCHAR(255) NOT NULL,
    tipo_material_sap VARCHAR(10) NOT NULL DEFAULT 'ROH',
    unidad_medida VARCHAR(20) NOT NULL DEFAULT 'UND',
    clase_valoracion VARCHAR(50) NOT NULL DEFAULT '3000-MP',
    cuenta_contable_activo VARCHAR(100) NOT NULL DEFAULT '143505 - Inventario Materia Prima',
    cuenta_contable_gasto VARCHAR(100) NOT NULL DEFAULT '510506 - Consumo de Insumos',
    cuenta_contable_transitoria VARCHAR(100) NOT NULL DEFAULT '220505 - Recepción de facturas por conciliar',
    centro_costo_defecto VARCHAR(50) NOT NULL DEFAULT 'CC-100-PLANTA',
    metodo_valoracion VARCHAR(20) NOT NULL DEFAULT 'CPP',
    precio_unitario_valorado NUMERIC(16, 4) NOT NULL DEFAULT 0,
    stock_seguridad NUMERIC(16, 4) NOT NULL DEFAULT 0,
    punto_reorden NUMERIC(16, 4) NOT NULL DEFAULT 0,
    codigo_centro VARCHAR(50) REFERENCES centros_almacen(codigo_centro),
    almacen_fisico VARCHAR(50),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_catalogo_material_sap_tipo CHECK (tipo_material_sap IN ('ROH', 'HALB', 'FERT', 'VERB', 'ERSA')),
    CONSTRAINT ck_catalogo_material_sap_metodo CHECK (metodo_valoracion IN ('CPP', 'FIFO', 'PRECIO_ESTANDAR')),
    CONSTRAINT ck_catalogo_material_sap_valores CHECK (
        precio_unitario_valorado >= 0 AND stock_seguridad >= 0 AND punto_reorden >= 0
    )
);

INSERT INTO catalogo_materiales_sap (
    id_material,
    id_articulo,
    sku_codigo,
    descripcion_tecnica,
    tipo_material_sap,
    unidad_medida,
    clase_valoracion,
    cuenta_contable_activo,
    cuenta_contable_gasto,
    cuenta_contable_transitoria,
    centro_costo_defecto,
    metodo_valoracion,
    precio_unitario_valorado,
    stock_seguridad,
    punto_reorden,
    codigo_centro,
    almacen_fisico,
    creado_en,
    actualizado_en
)
SELECT
    gen_random_uuid(),
    articulo.id_articulo,
    articulo.codigo_sku,
    articulo.nombre,
    CASE
        WHEN articulo.tipo_inventario = 'CONSUMIBLE' THEN 'VERB'
        WHEN articulo.tipo_inventario = 'REPUESTO' THEN 'ERSA'
        WHEN articulo.tipo_inventario = 'SEMIELABORADO' THEN 'HALB'
        WHEN articulo.tipo_inventario = 'PRODUCTO_TERMINADO' THEN 'FERT'
        ELSE 'ROH'
    END,
    COALESCE(articulo.unidad_medida, 'UND'),
    CASE
        WHEN articulo.tipo_inventario = 'CONSUMIBLE' THEN '4000-CONSUMIBLES'
        WHEN articulo.tipo_inventario = 'REPUESTO' THEN '5000-REPUESTOS'
        ELSE '3000-MP'
    END,
    CASE
        WHEN articulo.tipo_inventario = 'CONSUMIBLE' THEN '143510 - Inventario Consumibles'
        WHEN articulo.tipo_inventario = 'REPUESTO' THEN '143520 - Inventario Repuestos'
        ELSE '143505 - Inventario Materia Prima'
    END,
    CASE
        WHEN articulo.tipo_inventario = 'CONSUMIBLE' THEN '510506 - Consumo de Insumos'
        WHEN articulo.tipo_inventario = 'REPUESTO' THEN '510520 - Consumo de Repuestos'
        ELSE '710505 - Consumo de Materia Prima'
    END,
    '220505 - Recepción de facturas por conciliar',
    'CC-100-PLANTA',
    CASE WHEN articulo.metodo_valoracion = 'FIFO' THEN 'FIFO' ELSE 'CPP' END,
    articulo.costo_unitario,
    0,
    articulo.stock_minimo,
    'CENTRO-01-FUNZA',
    COALESCE(articulo.ubicacion, 'BOD-MP-01'),
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM articulos_inventario AS articulo
ON CONFLICT (sku_codigo) DO NOTHING;

UPDATE lotes_material AS lote
SET
    codigo_centro = COALESCE(lote.codigo_centro, catalogo.codigo_centro),
    almacen_fisico = COALESCE(
        lote.almacen_fisico,
        CASE
            WHEN lote.estado_calidad = 'CUARENTENA' THEN 'BOD-CUARENTENA-QM'
            ELSE catalogo.almacen_fisico
        END
    )
FROM catalogo_materiales_sap AS catalogo
WHERE catalogo.sku_codigo = lote.codigo_material;

CREATE TABLE IF NOT EXISTS movimientos_kardex_sap (
    id_movimiento UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_documento_material VARCHAR(50) NOT NULL UNIQUE,
    clase_movimiento VARCHAR(3) NOT NULL,
    sku_codigo VARCHAR(50) NOT NULL REFERENCES catalogo_materiales_sap(sku_codigo),
    codigo_centro VARCHAR(50) NOT NULL REFERENCES centros_almacen(codigo_centro),
    almacen_origen VARCHAR(50),
    almacen_destino VARCHAR(50),
    cantidad NUMERIC(16, 4) NOT NULL,
    costo_unitario NUMERIC(16, 4) NOT NULL,
    costo_total_movimiento NUMERIC(18, 4) NOT NULL,
    cuenta_debito VARCHAR(100) NOT NULL,
    cuenta_credito VARCHAR(100) NOT NULL,
    centro_costo_imputado VARCHAR(50),
    referencia_op VARCHAR(50),
    referencia_externa VARCHAR(100),
    registrado_por VARCHAR(150) NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_movimiento_kardex_sap_clase CHECK (clase_movimiento IN ('101', '201', '261', '311', '551')),
    CONSTRAINT ck_movimiento_kardex_sap_valores CHECK (
        cantidad > 0 AND costo_unitario >= 0 AND costo_total_movimiento >= 0
    )
);

INSERT INTO movimientos_kardex_sap (
    id_movimiento,
    numero_documento_material,
    clase_movimiento,
    sku_codigo,
    codigo_centro,
    almacen_origen,
    almacen_destino,
    cantidad,
    costo_unitario,
    costo_total_movimiento,
    cuenta_debito,
    cuenta_credito,
    centro_costo_imputado,
    referencia_op,
    referencia_externa,
    registrado_por,
    fecha_hora
)
SELECT
    movimiento.id_movimiento,
    'LEGACY-' || replace(movimiento.id_movimiento::text, '-', ''),
    movimiento.tipo_movimiento,
    articulo.codigo_sku,
    COALESCE(catalogo.codigo_centro, 'CENTRO-01-FUNZA'),
    CASE WHEN movimiento.tipo_movimiento = '311' THEN movimiento.destino ELSE NULL END,
    CASE WHEN movimiento.tipo_movimiento IN ('101', '311') THEN movimiento.destino ELSE NULL END,
    movimiento.cantidad,
    movimiento.costo_unitario,
    COALESCE(movimiento.valor_total, movimiento.cantidad * movimiento.costo_unitario),
    CASE
        WHEN movimiento.tipo_movimiento = '101' THEN catalogo.cuenta_contable_activo
        WHEN movimiento.tipo_movimiento = '311' THEN catalogo.cuenta_contable_activo
        ELSE catalogo.cuenta_contable_gasto
    END,
    CASE
        WHEN movimiento.tipo_movimiento = '101' THEN catalogo.cuenta_contable_transitoria
        ELSE catalogo.cuenta_contable_activo
    END,
    catalogo.centro_costo_defecto,
    movimiento.codigo_op,
    COALESCE(movimiento.documento_externo, movimiento.referencia_id),
    movimiento.registrado_por,
    movimiento.creado_en
FROM movimientos_inventario AS movimiento
JOIN articulos_inventario AS articulo
    ON articulo.id_articulo = movimiento.id_articulo
JOIN catalogo_materiales_sap AS catalogo
    ON catalogo.id_articulo = articulo.id_articulo
WHERE movimiento.tipo_movimiento IN ('101', '201', '261', '311')
  AND movimiento.cantidad > 0
  AND movimiento.costo_unitario >= 0
ON CONFLICT (numero_documento_material) DO NOTHING;

CREATE INDEX IF NOT EXISTS ix_movimientos_kardex_sap_sku_fecha
    ON movimientos_kardex_sap (sku_codigo, fecha_hora DESC);
CREATE INDEX IF NOT EXISTS ix_movimientos_kardex_sap_centro_fecha
    ON movimientos_kardex_sap (codigo_centro, fecha_hora DESC);
CREATE INDEX IF NOT EXISTS ix_movimientos_kardex_sap_op
    ON movimientos_kardex_sap (referencia_op)
    WHERE referencia_op IS NOT NULL;

CREATE OR REPLACE FUNCTION rechazar_edicion_kardex_sap()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Los documentos de material SAP son inmutables.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_movimientos_kardex_sap_inmutables ON movimientos_kardex_sap;
CREATE TRIGGER trg_movimientos_kardex_sap_inmutables
    BEFORE UPDATE OR DELETE ON movimientos_kardex_sap
    FOR EACH ROW EXECUTE FUNCTION rechazar_edicion_kardex_sap();
