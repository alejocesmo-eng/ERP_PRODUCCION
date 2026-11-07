-- 18_REVERSION_PRODUCTOS_RN.sql
-- Reversión de 18_MIGRACION_PRODUCTOS_RN.sql.
-- Antes de cambiar nada comprueba que planos.id_proyecto, planos.codigo_op y planos.archivo_url
-- (si existe) no tengan filas nulas. Si las hay, se detiene con un error que indica cuántas,
-- y la transacción no aplica ningún cambio.
-- Después elimina los vínculos id_producto y la tabla productos (DESTRUCTIVA para el catálogo
-- de productos y sus vínculos), restaura NOT NULL, el DEFAULT '4007256' de codigo_op y
-- ON DELETE CASCADE en planos.id_proyecto. Idempotente.
-- Solo con autorización de Dirección y respaldo previo. NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    columna TEXT;
    nulos BIGINT;
    detalle TEXT := '';
BEGIN
    FOREACH columna IN ARRAY ARRAY['id_proyecto', 'codigo_op', 'archivo_url'] LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = columna
        ) THEN
            EXECUTE format('SELECT count(*) FROM planos WHERE %I IS NULL', columna) INTO nulos;
            IF nulos > 0 THEN
                detalle := detalle || format(' planos.%s: %s filas nulas;', columna, nulos);
            END IF;
        END IF;
    END LOOP;
    IF detalle <> '' THEN
        RAISE EXCEPTION 'Reversión 18 detenida: no se puede restaurar NOT NULL.%', detalle
            USING HINT = 'Complete o elimine esas filas y vuelva a ejecutar la reversión.';
    END IF;
END $$;

DO $$
DECLARE
    tabla TEXT;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['planos', 'ordenes_produccion', 'pedido_detalles'] LOOP
        EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', tabla, 'fk_' || tabla || '_id_producto');
        EXECUTE format('DROP INDEX IF EXISTS %I', 'ix_' || tabla || '_id_producto');
        EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS id_producto', tabla);
    END LOOP;
END $$;

DROP TABLE IF EXISTS productos;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'id_proyecto'
    ) THEN
        ALTER TABLE planos ALTER COLUMN id_proyecto SET NOT NULL;
        ALTER TABLE planos DROP CONSTRAINT IF EXISTS fk_planos_id_proyecto;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.conrelid = 'planos'::regclass AND c.contype = 'f'
              AND c.confrelid = 'proyectos'::regclass AND a.attname = 'id_proyecto'
        ) THEN
            ALTER TABLE planos ADD CONSTRAINT planos_id_proyecto_fkey
                FOREIGN KEY (id_proyecto) REFERENCES proyectos(id_proyecto) ON DELETE CASCADE;
        END IF;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'codigo_op'
    ) THEN
        ALTER TABLE planos ALTER COLUMN codigo_op SET DEFAULT '4007256';
        ALTER TABLE planos ALTER COLUMN codigo_op SET NOT NULL;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'archivo_url'
    ) THEN
        ALTER TABLE planos ALTER COLUMN archivo_url SET NOT NULL;
    END IF;
END $$;

COMMIT;
