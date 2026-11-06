-- 17_REVERSION_PLANOS_FECHA_ULTIMA_REVISION.sql
-- Reversion de 17_MIGRACION_PLANOS_FECHA_ULTIMA_REVISION.sql.
-- DESTRUCTIVA para los valores de planos.fecha_ultima_revision: solo con autorizacion
-- de Direccion y respaldo previo. Idempotente.
-- NO la ejecuta ningun agente sobre sgi_db.

BEGIN;

ALTER TABLE planos
    DROP COLUMN IF EXISTS fecha_ultima_revision;

COMMIT;
