-- 23_REVERSION_COTIZACION_ESTADO_EMITIDA.sql
-- Reversión de 23_MIGRACION_COTIZACION_ESTADO_EMITIDA.sql: quita el estado EMITIDA.
--   * Se detiene sin cambiar nada si alguna cotización está en EMITIDA (no reasigna estados:
--     esa decisión es de Ventas).
--   * ENUM: PostgreSQL no permite quitar un valor; recrea el tipo con BORRADOR, ENVIADA,
--     APROBADA y RECHAZADA y convierte la columna.
--   * Texto: deja chk_cotizaciones_estado con los cuatro estados.
-- Idempotente. Solo con autorización de Dirección.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_tipo        oid;
    v_tipo_nombre text;
    v_tipo_simple text;
    v_es_enum     boolean;
    v_default     text;
    v_emitidas    bigint;
BEGIN
    SELECT a.atttypid, format_type(a.atttypid, NULL), t.typname, t.typtype = 'e',
           pg_get_expr(d.adbin, d.adrelid)
      INTO v_tipo, v_tipo_nombre, v_tipo_simple, v_es_enum, v_default
      FROM pg_attribute a
      JOIN pg_type t ON t.oid = a.atttypid
      LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
     WHERE a.attrelid = 'public.cotizaciones'::regclass
       AND a.attname = 'estado'
       AND NOT a.attisdropped;

    IF v_tipo IS NULL THEN
        RAISE EXCEPTION 'No existe la columna cotizaciones.estado.';
    END IF;

    SELECT count(*) INTO v_emitidas FROM public.cotizaciones WHERE estado::text = 'EMITIDA';
    IF v_emitidas > 0 THEN
        RAISE EXCEPTION 'Hay % cotizacion(es) en EMITIDA: reasígnelas antes de revertir.', v_emitidas;
    END IF;

    IF v_es_enum THEN
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = v_tipo AND enumlabel = 'EMITIDA') THEN
            RETURN;
        END IF;
        IF v_default IS NOT NULL THEN
            ALTER TABLE public.cotizaciones ALTER COLUMN estado DROP DEFAULT;
        END IF;
        EXECUTE format('ALTER TYPE %s RENAME TO %I', v_tipo_nombre, v_tipo_simple || '_con_emitida');
        EXECUTE format(
            'CREATE TYPE %I AS ENUM (%L, %L, %L, %L)',
            v_tipo_simple, 'BORRADOR', 'ENVIADA', 'APROBADA', 'RECHAZADA'
        );
        EXECUTE format(
            'ALTER TABLE public.cotizaciones ALTER COLUMN estado TYPE %I USING estado::text::%I',
            v_tipo_simple, v_tipo_simple
        );
        EXECUTE format('DROP TYPE %I', v_tipo_simple || '_con_emitida');
        IF v_default IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.cotizaciones ALTER COLUMN estado SET DEFAULT %L::%I', 'BORRADOR', v_tipo_simple);
        END IF;
    ELSE
        ALTER TABLE public.cotizaciones DROP CONSTRAINT IF EXISTS chk_cotizaciones_estado;
        ALTER TABLE public.cotizaciones
            ADD CONSTRAINT chk_cotizaciones_estado
            CHECK (estado IN ('BORRADOR', 'ENVIADA', 'APROBADA', 'RECHAZADA'));
    END IF;
END
$$;

COMMIT;
