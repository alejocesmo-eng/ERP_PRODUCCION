-- 13_MIGRACION_STOCK_PT_PICKING.sql
-- OT-2026-008 (alias OT-2026-VTA-001): consulta de stock de producto terminado
-- desde cotizaciones y pedidos, y orden de picking al confirmar el pedido.
-- Aditiva e idempotente, sin perdida de datos. NO la ejecuta ningun agente:
-- la aplica Direccion con respaldo previo de sgi_db y ensayo en BD de prueba.
-- Requiere las migraciones 05 y 06 (articulos_inventario) ya aplicadas.
-- Reversion: 13_REVERSION_STOCK_PT_PICKING.sql

BEGIN;

ALTER TABLE pedido_detalles
    ADD COLUMN IF NOT EXISTS origen VARCHAR(20) NOT NULL DEFAULT 'PLANO',
    ADD COLUMN IF NOT EXISTS id_articulo UUID NULL REFERENCES articulos_inventario(id_articulo);
ALTER TABLE posiciones_cotizacion
    ADD COLUMN IF NOT EXISTS origen VARCHAR(20) NOT NULL DEFAULT 'PLANO',
    ADD COLUMN IF NOT EXISTS id_articulo UUID NULL REFERENCES articulos_inventario(id_articulo);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_pedido_detalles_origen') THEN
        ALTER TABLE pedido_detalles ADD CONSTRAINT ck_pedido_detalles_origen
            CHECK (origen IN ('PLANO','STOCK_PT') AND (origen = 'PLANO' OR id_articulo IS NOT NULL));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_posiciones_cotizacion_origen') THEN
        ALTER TABLE posiciones_cotizacion ADD CONSTRAINT ck_posiciones_cotizacion_origen
            CHECK (origen IN ('PLANO','STOCK_PT') AND (origen = 'PLANO' OR id_articulo IS NOT NULL));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ordenes_picking (
    id_picking UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_picking VARCHAR(50) NOT NULL UNIQUE,
    id_proyecto UUID NOT NULL UNIQUE REFERENCES proyectos(id_proyecto) ON DELETE RESTRICT,
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE','EN_PICKING','DESPACHADO','CANCELADO')),
    creado_por VARCHAR(150),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ordenes_picking_detalle (
    id_picking_detalle UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_picking UUID NOT NULL REFERENCES ordenes_picking(id_picking) ON DELETE CASCADE,
    detalle_pedido_id UUID NOT NULL REFERENCES pedido_detalles(detalle_id) ON DELETE RESTRICT,
    id_articulo UUID NOT NULL REFERENCES articulos_inventario(id_articulo) ON DELETE RESTRICT,
    cantidad NUMERIC(14,3) NOT NULL CHECK (cantidad > 0),
    UNIQUE (id_picking, detalle_pedido_id)
);

CREATE INDEX IF NOT EXISTS ix_ordenes_picking_estado ON ordenes_picking (estado);
CREATE INDEX IF NOT EXISTS ix_picking_detalle_articulo ON ordenes_picking_detalle (id_articulo);
CREATE INDEX IF NOT EXISTS ix_pedido_detalles_id_articulo ON pedido_detalles (id_articulo);

COMMIT;
