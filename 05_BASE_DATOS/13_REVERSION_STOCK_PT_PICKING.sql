-- 13_REVERSION_STOCK_PT_PICKING.sql
-- Reversion de 13_MIGRACION_STOCK_PT_PICKING.sql (OT-2026-008).
-- DESTRUCTIVA para los datos nuevos: solo con autorizacion de Direccion y respaldo previo.
-- NO la ejecuta ningun agente.

BEGIN;
-- Guardia: abortar si ya hay pickings no despachados (compromisos vivos)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM ordenes_picking WHERE estado IN ('PENDIENTE','EN_PICKING')) THEN
        RAISE EXCEPTION 'Hay ordenes_picking vigentes; resolver antes de revertir';
    END IF;
END $$;
DROP TABLE IF EXISTS ordenes_picking_detalle;
DROP TABLE IF EXISTS ordenes_picking;
ALTER TABLE pedido_detalles DROP CONSTRAINT IF EXISTS ck_pedido_detalles_origen;
ALTER TABLE posiciones_cotizacion DROP CONSTRAINT IF EXISTS ck_posiciones_cotizacion_origen;
DROP INDEX IF EXISTS ix_pedido_detalles_id_articulo;
ALTER TABLE pedido_detalles DROP COLUMN IF EXISTS id_articulo, DROP COLUMN IF EXISTS origen;
ALTER TABLE posiciones_cotizacion DROP COLUMN IF EXISTS id_articulo, DROP COLUMN IF EXISTS origen;
COMMIT;
