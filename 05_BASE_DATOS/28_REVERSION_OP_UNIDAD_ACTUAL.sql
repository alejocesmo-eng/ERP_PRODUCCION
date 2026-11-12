-- 28_REVERSION_OP_UNIDAD_ACTUAL.sql
-- Reversión de 28_MIGRACION_OP_UNIDAD_ACTUAL.sql: elimina op_traslados_unidad y la columna
-- ordenes_produccion.unidad_actual.
--   * Se detiene SIN cambiar nada si hay traslados registrados: son trazabilidad. Respáldelos y
--     vacíe la tabla antes de revertir.
--   * La unidad deducida por la migración se pierde (se vuelve a deducir al reaplicarla).
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_traslados bigint;
BEGIN
    IF to_regclass('public.op_traslados_unidad') IS NOT NULL THEN
        SELECT count(*) INTO v_traslados FROM op_traslados_unidad;
        IF v_traslados > 0 THEN
            RAISE EXCEPTION 'Hay % traslado(s) de OP registrados; respáldelos y vacíe op_traslados_unidad antes de revertir.', v_traslados;
        END IF;
        DROP TABLE op_traslados_unidad;
    END IF;
END $$;

ALTER TABLE ordenes_produccion DROP CONSTRAINT IF EXISTS ck_ordenes_produccion_unidad_actual;
ALTER TABLE ordenes_produccion DROP COLUMN IF EXISTS unidad_actual;

COMMIT;
