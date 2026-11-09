-- 20_MIGRACION_OP_LINEA_PEDIDO.sql
-- Una OP activa por línea de pedido.
--   * ordenes_produccion.id_detalle_pedido: línea de pedido de la que sale la OP
--     (FK a pedido_detalles, ON DELETE RESTRICT: una línea con OP no se puede borrar).
--     Las OP existentes quedan en NULL. Si la FK ya existía con otra acción (versión anterior
--     de esta migración con SET NULL), se recrea con RESTRICT.
--   * Índice único parcial: una sola OP no CANCELADA por línea de pedido. Una OP CANCELADA
--     libera la línea para crear otra. Varias OP de productos distintos del mismo pedido
--     siguen permitidas (cada una sale de su línea).
-- Idempotente y sin pérdida de datos.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Requiere 18_MIGRACION_PRODUCTOS_RN.sql.
-- Reversión: 20_REVERSION_OP_LINEA_PEDIDO.sql

BEGIN;

ALTER TABLE ordenes_produccion ADD COLUMN IF NOT EXISTS id_detalle_pedido UUID NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ordenes_produccion'::regclass AND conname = 'fk_ordenes_produccion_id_detalle_pedido'
          AND confdeltype <> 'r'
    ) THEN
        ALTER TABLE ordenes_produccion DROP CONSTRAINT fk_ordenes_produccion_id_detalle_pedido;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ordenes_produccion'::regclass AND conname = 'fk_ordenes_produccion_id_detalle_pedido'
    ) THEN
        ALTER TABLE ordenes_produccion ADD CONSTRAINT fk_ordenes_produccion_id_detalle_pedido
            FOREIGN KEY (id_detalle_pedido) REFERENCES pedido_detalles(detalle_id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_ordenes_produccion_detalle_activa
    ON ordenes_produccion (id_detalle_pedido)
    WHERE id_detalle_pedido IS NOT NULL AND estado <> 'CANCELADA';

COMMIT;
