-- 24_MIGRACION_SOCIOS_CODIGO_NIT.sql
-- SCRUM-22: codigo_socio es el NIT del socio guardado solo con números (sin puntos, espacios,
-- guion ni dígito de verificación). Clientes y proveedores sin NIT válido no se pueden crear.
--   * Si socios_negocio no tiene codigo_socio (bases creadas con 07_MIGRACION_DATOS_MAESTROS.sql),
--     la agrega; si ya existe (bases creadas con create_all), recalcula sus valores.
--   * Regla (igual a app/services/socios.py): nit_cedula sin espacios al inicio y al final debe ser
--     dígitos con puntos o espacios opcionales y, al final, un guion y un solo dígito de
--     verificación, que se descarta. Deben quedar entre 5 y 15 dígitos.
--       800.123.456-1 -> 800123456      900123456 -> 900123456
--   * Se detiene SIN cambiar nada si algún NIT no cumple la regla o si dos socios quedan con el
--     mismo código: lista los casos para que Ventas/Compras los corrija (no se inventan códigos).
--   * Guarda el código anterior de cada socio en socios_negocio_codigo_anterior para la reversión.
--   * Deja codigo_socio NOT NULL, con índice único ix_socios_negocio_codigo_socio y la restricción
--     ck_socios_negocio_codigo_nit (solo 5 a 15 dígitos).
-- Idempotente y sin pérdida de datos (nit_cedula no se modifica).
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Reversión: 24_REVERSION_SOCIOS_CODIGO_NIT.sql

BEGIN;

DO $$
DECLARE
    v_columna_existia boolean;
    v_invalidos       bigint;
    v_ejemplos        text;
    v_duplicados      bigint;
    v_actualizados    bigint;
BEGIN
    IF to_regclass('public.socios_negocio') IS NULL THEN
        RAISE EXCEPTION 'No existe la tabla socios_negocio.';
    END IF;

    v_columna_existia := EXISTS (
        SELECT 1 FROM pg_attribute
         WHERE attrelid = 'public.socios_negocio'::regclass
           AND attname = 'codigo_socio'
           AND NOT attisdropped
    );

    CREATE TEMP TABLE tmp_codigo_nit ON COMMIT DROP AS
    SELECT id_socio,
           razon_social,
           nit_cedula,
           CASE
               WHEN btrim(nit_cedula) ~ '^[0-9][0-9. ]*(-\s*[0-9])?$'
               THEN regexp_replace(regexp_replace(btrim(nit_cedula), '-\s*[0-9]$', ''), '[^0-9]', '', 'g')
           END AS codigo_nuevo
      FROM public.socios_negocio;

    SELECT count(*),
           string_agg(format('%s (NIT %s)', razon_social, nit_cedula), '; ' ORDER BY razon_social)
               FILTER (WHERE fila <= 10)
      INTO v_invalidos, v_ejemplos
      FROM (
          SELECT razon_social, nit_cedula, row_number() OVER (ORDER BY razon_social) AS fila
            FROM tmp_codigo_nit
           WHERE codigo_nuevo IS NULL OR length(codigo_nuevo) NOT BETWEEN 5 AND 15
      ) invalidos;
    IF v_invalidos > 0 THEN
        RAISE EXCEPTION 'Hay % socio(s) con NIT que no cumple la regla; corríjalos antes de migrar. Primeros: %',
            v_invalidos, v_ejemplos;
    END IF;

    SELECT count(*),
           string_agg(format('%s: %s', codigo_nuevo, socios), '; ' ORDER BY codigo_nuevo)
               FILTER (WHERE fila <= 10)
      INTO v_duplicados, v_ejemplos
      FROM (
          SELECT codigo_nuevo,
                 string_agg(format('%s (NIT %s)', razon_social, nit_cedula), ', ' ORDER BY razon_social) AS socios,
                 row_number() OVER (ORDER BY codigo_nuevo) AS fila
            FROM tmp_codigo_nit
           GROUP BY codigo_nuevo
          HAVING count(*) > 1
      ) duplicados;
    IF v_duplicados > 0 THEN
        RAISE EXCEPTION 'Hay % NIT repetido(s) al quitar el dígito de verificación; unifique esos socios antes de migrar. Primeros: %',
            v_duplicados, v_ejemplos;
    END IF;

    CREATE TABLE IF NOT EXISTS public.socios_negocio_codigo_anterior (
        id_socio              uuid PRIMARY KEY REFERENCES public.socios_negocio (id_socio) ON DELETE CASCADE,
        codigo_socio_anterior varchar(50),
        migrado_en            timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    IF NOT v_columna_existia THEN
        ALTER TABLE public.socios_negocio ADD COLUMN codigo_socio varchar(50);
        COMMENT ON COLUMN public.socios_negocio.codigo_socio IS 'SCRUM-22: agregada por 24_MIGRACION_SOCIOS_CODIGO_NIT';
    END IF;

    -- Respaldo solo de los socios cuyo código cambia (en una segunda ejecución no hay cambios)
    INSERT INTO public.socios_negocio_codigo_anterior (id_socio, codigo_socio_anterior)
    SELECT s.id_socio, s.codigo_socio
      FROM public.socios_negocio s
      JOIN tmp_codigo_nit t ON t.id_socio = s.id_socio
     WHERE s.codigo_socio IS DISTINCT FROM t.codigo_nuevo
    ON CONFLICT (id_socio) DO NOTHING;

    -- Dos pasos para no chocar con el índice único mientras se reasignan códigos entre socios
    UPDATE public.socios_negocio s
       SET codigo_socio = 'SCRUM22-' || s.id_socio::text
      FROM tmp_codigo_nit t
     WHERE t.id_socio = s.id_socio
       AND s.codigo_socio IS DISTINCT FROM t.codigo_nuevo;

    UPDATE public.socios_negocio s
       SET codigo_socio = t.codigo_nuevo
      FROM tmp_codigo_nit t
     WHERE t.id_socio = s.id_socio
       AND s.codigo_socio IS DISTINCT FROM t.codigo_nuevo;
    GET DIAGNOSTICS v_actualizados = ROW_COUNT;

    ALTER TABLE public.socios_negocio ALTER COLUMN codigo_socio SET NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS ix_socios_negocio_codigo_socio ON public.socios_negocio (codigo_socio);

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.socios_negocio'::regclass
           AND conname = 'ck_socios_negocio_codigo_nit'
    ) THEN
        ALTER TABLE public.socios_negocio
            ADD CONSTRAINT ck_socios_negocio_codigo_nit CHECK (codigo_socio ~ '^[0-9]{5,15}$');
    END IF;

    RAISE NOTICE 'SCRUM-22: % socio(s) con codigo_socio actualizado; columna %.',
        v_actualizados, CASE WHEN v_columna_existia THEN 'existente' ELSE 'agregada' END;
END
$$;

COMMIT;
