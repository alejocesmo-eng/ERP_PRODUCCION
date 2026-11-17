-- 33_REVERSION_CARGA_TIEMPOS_MANUAL.sql
-- Reversión de 33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql: elimina maquina_operarios,
-- tiempos_manuales_correcciones y las columnas nuevas de registro_tiempos_produccion.
--   * Se detiene SIN cambiar nada si hay filas manuales de tiempos o correcciones: son
--     trazabilidad y base de costos. Respáldelas y elimínelas antes de revertir.
--   * Las asignaciones de operarios por máquina se pierden (son configuración).
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_manuales bigint := 0;
    v_correcciones bigint := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_name = 'registro_tiempos_produccion' AND column_name = 'origen') THEN
        SELECT count(*) INTO v_manuales FROM registro_tiempos_produccion WHERE origen = 'MANUAL';
    END IF;
    IF to_regclass('public.tiempos_manuales_correcciones') IS NOT NULL THEN
        SELECT count(*) INTO v_correcciones FROM tiempos_manuales_correcciones;
    END IF;
    IF v_manuales > 0 OR v_correcciones > 0 THEN
        RAISE EXCEPTION 'Hay % fila(s) manuales de tiempos y % corrección(es); respáldelas y elimínelas antes de revertir.',
            v_manuales, v_correcciones;
    END IF;
END $$;

DROP TABLE IF EXISTS maquina_operarios;
DROP TABLE IF EXISTS tiempos_manuales_correcciones;

ALTER TABLE registro_tiempos_produccion DROP CONSTRAINT IF EXISTS ck_registro_tiempos_manual;
ALTER TABLE registro_tiempos_produccion DROP CONSTRAINT IF EXISTS ck_registro_tiempos_setup;
ALTER TABLE registro_tiempos_produccion DROP CONSTRAINT IF EXISTS ck_registro_tiempos_origen;
ALTER TABLE registro_tiempos_produccion
    DROP COLUMN IF EXISTS registrado_por,
    DROP COLUMN IF EXISTS origen,
    DROP COLUMN IF EXISTS fecha_trabajo,
    DROP COLUMN IF EXISTS segundos_setup,
    DROP COLUMN IF EXISTS id_operacion;

COMMIT;
