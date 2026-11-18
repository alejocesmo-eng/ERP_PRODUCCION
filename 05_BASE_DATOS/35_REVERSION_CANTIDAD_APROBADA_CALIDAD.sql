-- 35_REVERSION_CANTIDAD_APROBADA_CALIDAD.sql
-- Reversión de 35_MIGRACION_CANTIDAD_APROBADA_CALIDAD.sql: elimina cantidad_aprobada y
-- tipo_aprobacion de inspecciones_calidad.
--   * Se detiene SIN cambiar nada si alguna inspección ya registró piezas aprobadas: son la base de
--     las piezas terminadas. Respáldelas antes de revertir.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_con_piezas bigint := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'inspecciones_calidad'
                  AND column_name = 'cantidad_aprobada') THEN
        EXECUTE 'SELECT count(*) FROM inspecciones_calidad WHERE cantidad_aprobada > 0' INTO v_con_piezas;
    END IF;
    IF v_con_piezas > 0 THEN
        RAISE EXCEPTION 'Hay % inspección(es) con piezas aprobadas; respáldelas y ponga cantidad_aprobada en 0 antes de revertir.', v_con_piezas;
    END IF;
END $$;

ALTER TABLE inspecciones_calidad DROP CONSTRAINT IF EXISTS ck_inspecciones_tipo_aprobacion;
ALTER TABLE inspecciones_calidad DROP CONSTRAINT IF EXISTS ck_inspecciones_cantidad_aprobada;
ALTER TABLE inspecciones_calidad
    DROP COLUMN IF EXISTS tipo_aprobacion,
    DROP COLUMN IF EXISTS cantidad_aprobada;

COMMIT;
