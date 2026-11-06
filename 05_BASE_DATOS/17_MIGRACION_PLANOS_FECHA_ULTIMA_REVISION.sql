-- 17_MIGRACION_PLANOS_FECHA_ULTIMA_REVISION.sql
-- Fecha de la ultima revision del plano (decision del corte v0.5).
-- La refleja Plano.fecha_ultima_revision en app/db/models.py.
-- Aditiva e idempotente, sin perdida de datos ni relleno de filas existentes (queda NULL).
-- NO la ejecuta ningun agente sobre sgi_db: la aplica Direccion con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Reversion: 17_REVERSION_PLANOS_FECHA_ULTIMA_REVISION.sql

BEGIN;

ALTER TABLE planos
    ADD COLUMN IF NOT EXISTS fecha_ultima_revision TIMESTAMP WITH TIME ZONE NULL;

COMMIT;
