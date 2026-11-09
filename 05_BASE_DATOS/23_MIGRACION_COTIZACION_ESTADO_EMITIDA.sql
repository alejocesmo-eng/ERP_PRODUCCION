-- 23_MIGRACION_COTIZACION_ESTADO_EMITIDA.sql
-- Estado EMITIDA de la cotización (POST /ventas/cotizaciones/{id}/enviar-cliente pasa de
-- BORRADOR a EMITIDA). Sin este valor la base rechaza el cambio y el endpoint responde 500.
--   * Conserva BORRADOR, ENVIADA, APROBADA y RECHAZADA; solo agrega EMITIDA.
--   * Si cotizaciones.estado es un tipo ENUM (tablas creadas con create_all, tipo
--     estadocotizacionenum), agrega el valor EMITIDA después de BORRADOR.
--   * Si la columna es texto, reemplaza su restricción CHECK de estado por
--     chk_cotizaciones_estado con los cinco estados.
-- Idempotente y sin pérdida de datos. Requiere PostgreSQL 12 o superior (ALTER TYPE ... ADD
-- VALUE dentro de una transacción).
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Reversión: 23_REVERSION_COTIZACION_ESTADO_EMITIDA.sql

BEGIN;

DO $$
DECLARE
    v_tipo        oid;
    v_tipo_nombre text;
    v_es_enum     boolean;
    v_attnum      smallint;
    v_restriccion record;
BEGIN
    SELECT a.atttypid, a.attnum, format_type(a.atttypid, NULL), t.typtype = 'e'
      INTO v_tipo, v_attnum, v_tipo_nombre, v_es_enum
      FROM pg_attribute a
      JOIN pg_type t ON t.oid = a.atttypid
     WHERE a.attrelid = 'public.cotizaciones'::regclass
       AND a.attname = 'estado'
       AND NOT a.attisdropped;

    IF v_tipo IS NULL THEN
        RAISE EXCEPTION 'No existe la columna cotizaciones.estado.';
    END IF;

    IF v_es_enum THEN
        EXECUTE format('ALTER TYPE %s ADD VALUE IF NOT EXISTS %L AFTER %L', v_tipo_nombre, 'EMITIDA', 'BORRADOR');
    ELSE
        FOR v_restriccion IN
            SELECT conname
              FROM pg_constraint
             WHERE conrelid = 'public.cotizaciones'::regclass
               AND contype = 'c'
               AND conkey = ARRAY[v_attnum]
        LOOP
            EXECUTE format('ALTER TABLE public.cotizaciones DROP CONSTRAINT %I', v_restriccion.conname);
        END LOOP;
        ALTER TABLE public.cotizaciones
            ADD CONSTRAINT chk_cotizaciones_estado
            CHECK (estado IN ('BORRADOR', 'EMITIDA', 'ENVIADA', 'APROBADA', 'RECHAZADA'));
    END IF;
END
$$;

COMMIT;
