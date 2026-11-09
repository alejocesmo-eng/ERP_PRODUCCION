-- 21_MIGRACION_PLANOS_HISTORIAL.sql
-- Historial append-only por plano (línea de tiempo de Diseño, ISO 9001:2026 7.5.3).
--   * planos_historial: un evento por cambio del plano con versión, estado de diseño,
--     usuario del token, fecha, tipo de evento, tipo de archivo, sha256 y justificación.
--   * Tipos de evento: CREACION, CAMBIO_VERSION, CARGA_ARCHIVO, CAMBIO_ARCHIVO, REVISION,
--     CAMBIO_ESTADO y APROBACION.
--   * CAMBIO_VERSION, CAMBIO_ARCHIVO y REVISION exigen justificación de al menos 10
--     caracteres sin contar espacios; en APROBACION es opcional.
--   * Append-only: un trigger rechaza UPDATE y DELETE. La FK a planos es ON DELETE RESTRICT
--     para que borrar un plano no borre su historial.
-- Sin relleno de eventos anteriores: no hay registro fiable de los cambios pasados.
-- Idempotente y sin pérdida de datos.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Requiere 19_MIGRACION_PLANOS_ARCHIVOS.sql.
-- Reversión: 21_REVERSION_PLANOS_HISTORIAL.sql

BEGIN;

CREATE TABLE IF NOT EXISTS planos_historial (
    id_evento UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_plano UUID NOT NULL REFERENCES planos(id_plano) ON DELETE RESTRICT,
    tipo_evento VARCHAR(30) NOT NULL,
    version VARCHAR(10) NULL,
    version_anterior VARCHAR(10) NULL,
    estado VARCHAR(50) NULL,
    tipo_archivo VARCHAR(10) NULL,
    sha256 CHAR(64) NULL,
    usuario VARCHAR(100) NOT NULL,
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    justificacion TEXT NULL,
    CONSTRAINT ck_planos_historial_tipo_evento CHECK (tipo_evento IN (
        'CREACION', 'CAMBIO_VERSION', 'CARGA_ARCHIVO', 'CAMBIO_ARCHIVO',
        'REVISION', 'CAMBIO_ESTADO', 'APROBACION'
    )),
    CONSTRAINT ck_planos_historial_tipo_archivo CHECK (tipo_archivo IS NULL OR tipo_archivo IN ('PDF', 'STEP', 'DXF')),
    CONSTRAINT ck_planos_historial_sha256 CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_planos_historial_justificacion CHECK (
        tipo_evento NOT IN ('CAMBIO_VERSION', 'CAMBIO_ARCHIVO', 'REVISION')
        OR (justificacion IS NOT NULL AND length(trim(justificacion)) >= 10)
    )
);
CREATE INDEX IF NOT EXISTS ix_planos_historial_plano_fecha ON planos_historial (id_plano, fecha);

CREATE OR REPLACE FUNCTION rechazar_edicion_planos_historial()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'El historial de planos es append-only: no se permite UPDATE ni DELETE.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_planos_historial_inmutable ON planos_historial;
CREATE TRIGGER trg_planos_historial_inmutable
    BEFORE UPDATE OR DELETE ON planos_historial
    FOR EACH ROW EXECUTE FUNCTION rechazar_edicion_planos_historial();

COMMIT;
