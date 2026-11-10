-- 24_REVERSION_SOCIOS_CODIGO_NIT.sql
-- Reversión de 24_MIGRACION_SOCIOS_CODIGO_NIT.sql.
--   * Quita la restricción ck_socios_negocio_codigo_nit.
--   * Si la migración agregó la columna codigo_socio (comentario SCRUM-22), la elimina con su
--     índice. Si la columna ya existía, devuelve a cada socio el código guardado en
--     socios_negocio_codigo_anterior; los socios creados después conservan su código numérico.
--   * Elimina socios_negocio_codigo_anterior.
-- Ojo: el backend de SCRUM-22 requiere codigo_socio; revertir solo junto con ese código.
-- Idempotente. Solo con autorización de Dirección.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_agregada_por_24 boolean;
BEGIN
    IF to_regclass('public.socios_negocio') IS NULL THEN
        RAISE EXCEPTION 'No existe la tabla socios_negocio.';
    END IF;

    ALTER TABLE public.socios_negocio DROP CONSTRAINT IF EXISTS ck_socios_negocio_codigo_nit;

    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute
         WHERE attrelid = 'public.socios_negocio'::regclass
           AND attname = 'codigo_socio'
           AND NOT attisdropped
    ) THEN
        DROP TABLE IF EXISTS public.socios_negocio_codigo_anterior;
        RETURN;
    END IF;

    v_agregada_por_24 := coalesce(
        col_description('public.socios_negocio'::regclass,
            (SELECT attnum FROM pg_attribute
              WHERE attrelid = 'public.socios_negocio'::regclass AND attname = 'codigo_socio')
        ) LIKE 'SCRUM-22:%',
        false
    );

    IF v_agregada_por_24 THEN
        DROP INDEX IF EXISTS public.ix_socios_negocio_codigo_socio;
        ALTER TABLE public.socios_negocio DROP COLUMN codigo_socio;
    ELSIF to_regclass('public.socios_negocio_codigo_anterior') IS NOT NULL THEN
        -- Dos pasos para no chocar con el índice único
        UPDATE public.socios_negocio s
           SET codigo_socio = 'SCRUM22-' || s.id_socio::text
          FROM public.socios_negocio_codigo_anterior a
         WHERE a.id_socio = s.id_socio
           AND a.codigo_socio_anterior IS NOT NULL;

        UPDATE public.socios_negocio s
           SET codigo_socio = a.codigo_socio_anterior
          FROM public.socios_negocio_codigo_anterior a
         WHERE a.id_socio = s.id_socio
           AND a.codigo_socio_anterior IS NOT NULL;
    END IF;

    DROP TABLE IF EXISTS public.socios_negocio_codigo_anterior;
END
$$;

COMMIT;
