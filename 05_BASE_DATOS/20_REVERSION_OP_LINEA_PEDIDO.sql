-- 20_REVERSION_OP_LINEA_PEDIDO.sql
-- Reversión de 20_MIGRACION_OP_LINEA_PEDIDO.sql.
-- DESTRUCTIVA para el vínculo OP -> línea de pedido (id_detalle_pedido); las OP se conservan.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DROP INDEX IF EXISTS ux_ordenes_produccion_detalle_activa;
ALTER TABLE ordenes_produccion DROP CONSTRAINT IF EXISTS fk_ordenes_produccion_id_detalle_pedido;
ALTER TABLE ordenes_produccion DROP COLUMN IF EXISTS id_detalle_pedido;

COMMIT;
