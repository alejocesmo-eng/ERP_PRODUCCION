-- 19_REVERSION_PLANOS_ARCHIVOS.sql
-- Reversión de 19_MIGRACION_PLANOS_ARCHIVOS.sql.
--   * Elimina planos_archivos (DESTRUCTIVA para el histórico de archivos, sha256 y tamaño;
--     los archivos físicos no se tocan).
--   * Elimina planos.archivo_pdf_url solo si la creó la migración 19 (comentario de la columna).
--     Si ya existía antes, se conserva: en esas bases es la única columna del PDF.
--   * planos.archivo_url queda intacta.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DROP TABLE IF EXISTS planos_archivos;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'archivo_pdf_url'
    ) AND col_description(
        'planos'::regclass,
        (SELECT attnum FROM pg_attribute WHERE attrelid = 'planos'::regclass AND attname = 'archivo_pdf_url')
    ) = 'Creada por 19_MIGRACION_PLANOS_ARCHIVOS.sql' THEN
        ALTER TABLE planos DROP COLUMN archivo_pdf_url;
    END IF;
END $$;

COMMIT;
