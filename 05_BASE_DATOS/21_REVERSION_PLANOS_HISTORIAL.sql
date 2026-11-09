-- 21_REVERSION_PLANOS_HISTORIAL.sql
-- Reversión de 21_MIGRACION_PLANOS_HISTORIAL.sql.
--   * Elimina el trigger, la función y la tabla planos_historial (DESTRUCTIVA para la línea
--     de tiempo de los planos; planos y planos_archivos no se tocan).
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DROP TRIGGER IF EXISTS trg_planos_historial_inmutable ON planos_historial;
DROP TABLE IF EXISTS planos_historial;
DROP FUNCTION IF EXISTS rechazar_edicion_planos_historial();

COMMIT;
