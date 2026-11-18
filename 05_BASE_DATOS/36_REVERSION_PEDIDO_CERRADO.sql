-- 36_REVERSION_PEDIDO_CERRADO.sql
-- Reversión de 36_MIGRACION_PEDIDO_CERRADO.sql.
--   * Se detiene SIN cambiar nada si hay pedidos CERRADO o avisos OP_CERRADA_RESPALDO: son histórico.
--     Respáldelos y cámbielos o bórrelos antes de revertir.
--   * proyectos.estado: si la creó la migración 36 (marca en su comentario) se elimina; si ya
--     existía, se conserva y solo se le quita el valor CERRADO.
--   * estado_proyecto: si lo creó la migración 36 y nada lo usa, se elimina; si no, se quita CERRADO.
--   * tiponotificacionenum: se quita OP_CERRADA_RESPALDO.
-- PostgreSQL no quita valores de un ENUM: el tipo se recrea sin el valor y las columnas que lo usan
-- se convierten al tipo nuevo (con su valor por defecto).
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_cerrados bigint := 0;
    v_avisos bigint := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'estado_proyecto' AND e.enumlabel = 'CERRADO')
       AND EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = 'proyectos' AND column_name = 'estado') THEN
        EXECUTE 'SELECT count(*) FROM proyectos WHERE estado::text = ''CERRADO''' INTO v_cerrados;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'tiponotificacionenum' AND e.enumlabel = 'OP_CERRADA_RESPALDO') THEN
        EXECUTE 'SELECT count(*) FROM notificaciones_lider WHERE tipo_notificacion::text = ''OP_CERRADA_RESPALDO'''
           INTO v_avisos;
    END IF;
    IF v_cerrados > 0 OR v_avisos > 0 THEN
        RAISE EXCEPTION 'Hay % pedido(s) CERRADO y % aviso(s) OP_CERRADA_RESPALDO; respáldelos y cámbielos antes de revertir.',
            v_cerrados, v_avisos;
    END IF;
END $$;

-- Columna creada por la migración 36
DO $$
BEGIN
    IF col_description('proyectos'::regclass,
                       (SELECT attnum FROM pg_attribute WHERE attrelid = 'proyectos'::regclass
                         AND attname = 'estado' AND NOT attisdropped)) LIKE '%migración 36%' THEN
        ALTER TABLE proyectos DROP COLUMN estado;
    END IF;
END $$;

-- Tipo creado por la migración 36 y sin uso
DO $$
BEGIN
    IF obj_description((SELECT oid FROM pg_type WHERE typname = 'estado_proyecto'), 'pg_type') LIKE '%migración 36%'
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE udt_name = 'estado_proyecto') THEN
        DROP TYPE estado_proyecto;
    END IF;
END $$;

-- Quita un valor de un ENUM recreando el tipo
DO $$
DECLARE
    v_par text[];
    v_tipo text;
    v_valor text;
    v_valores text;
    v_columna record;
BEGIN
    FOREACH v_par SLICE 1 IN ARRAY ARRAY[['estado_proyecto', 'CERRADO'], ['tiponotificacionenum', 'OP_CERRADA_RESPALDO']] LOOP
        v_tipo := v_par[1];
        v_valor := v_par[2];
        CONTINUE WHEN NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
                                   WHERE t.typname = v_tipo AND e.enumlabel = v_valor);
        SELECT string_agg(quote_literal(e.enumlabel), ', ' ORDER BY e.enumsortorder) INTO v_valores
          FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
         WHERE t.typname = v_tipo AND e.enumlabel <> v_valor;
        EXECUTE format('ALTER TYPE %I RENAME TO %I', v_tipo, v_tipo || '_rev36');
        EXECUTE format('CREATE TYPE %I AS ENUM (%s)', v_tipo, v_valores);
        FOR v_columna IN
            SELECT table_schema, table_name, column_name, column_default FROM information_schema.columns
             WHERE udt_name = v_tipo || '_rev36'
        LOOP
            EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN %I DROP DEFAULT',
                           v_columna.table_schema, v_columna.table_name, v_columna.column_name);
            EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN %I TYPE %I USING %I::text::%I',
                           v_columna.table_schema, v_columna.table_name, v_columna.column_name,
                           v_tipo, v_columna.column_name, v_tipo);
            IF v_columna.column_default IS NOT NULL THEN
                EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN %I SET DEFAULT %s',
                               v_columna.table_schema, v_columna.table_name, v_columna.column_name,
                               replace(v_columna.column_default, v_tipo || '_rev36', v_tipo));
            END IF;
        END LOOP;
        EXECUTE format('DROP TYPE %I', v_tipo || '_rev36');
    END LOOP;
END $$;

COMMIT;
