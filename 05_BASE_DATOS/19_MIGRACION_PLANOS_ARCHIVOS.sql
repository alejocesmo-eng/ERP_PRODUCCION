-- 19_MIGRACION_PLANOS_ARCHIVOS.sql
-- Archivos por plano (PDF, STEP, DXF) con hash y tamaño, y columna canónica del PDF.
--   * planos_archivos: histórico de archivos por plano. sha256 y tamano_bytes obligatorios.
--     Índice único parcial: un solo archivo vigente por plano y tipo.
--   * planos.archivo_pdf_url: columna canónica del PDF en el código. Se crea si no existe
--     (esquema heredado de sgi_db) y se marca con un comentario para que la reversión sepa
--     que la creó esta migración.
--   * Copia archivo_url -> archivo_pdf_url donde archivo_pdf_url esté vacía, sin borrar
--     archivo_url (se mantiene solo por compatibilidad de lectura).
-- Sin relleno de planos_archivos: el hash y el tamaño exigen leer los archivos físicos.
-- Idempotente y sin pérdida de datos.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Requiere 18_MIGRACION_PRODUCTOS_RN.sql.
-- Reversión: 19_REVERSION_PLANOS_ARCHIVOS.sql

BEGIN;

CREATE TABLE IF NOT EXISTS planos_archivos (
    id_archivo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_plano UUID NOT NULL REFERENCES planos(id_plano) ON DELETE CASCADE,
    tipo VARCHAR(10) NOT NULL,
    ruta VARCHAR(500) NOT NULL,
    nombre_original VARCHAR(255) NOT NULL,
    tamano_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    revision VARCHAR(10) NULL,
    vigente BOOLEAN NOT NULL DEFAULT TRUE,
    subido_por VARCHAR(100) NULL,
    subido_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_planos_archivos_tipo CHECK (tipo IN ('PDF', 'STEP', 'DXF')),
    CONSTRAINT ck_planos_archivos_tamano CHECK (tamano_bytes > 0),
    CONSTRAINT ck_planos_archivos_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_planos_archivos_id_plano ON planos_archivos (id_plano);
CREATE UNIQUE INDEX IF NOT EXISTS ux_planos_archivos_vigente ON planos_archivos (id_plano, tipo) WHERE vigente;

-- Columna canónica del PDF, por separado
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'archivo_pdf_url'
    ) THEN
        ALTER TABLE planos ADD COLUMN archivo_pdf_url VARCHAR(255) NULL;
        COMMENT ON COLUMN planos.archivo_pdf_url IS 'Creada por 19_MIGRACION_PLANOS_ARCHIVOS.sql';
    END IF;
END $$;

-- Copia archivo_url -> archivo_pdf_url sin borrar archivo_url
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'archivo_url'
    ) THEN
        UPDATE planos SET archivo_pdf_url = archivo_url
        WHERE archivo_url IS NOT NULL
          AND (archivo_pdf_url IS NULL OR archivo_pdf_url = '');
    END IF;
END $$;

COMMIT;
