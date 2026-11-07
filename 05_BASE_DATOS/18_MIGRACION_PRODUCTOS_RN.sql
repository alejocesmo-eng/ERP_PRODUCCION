-- 18_MIGRACION_PRODUCTOS_RN.sql
-- Catálogo de productos con código RN y vínculo del producto con planos, OP y líneas de pedido.
--   * productos: codigo_rn único con formato RN-###-###-######; codigo_anterior conserva el
--     código previo (no se convierte a RN automáticamente).
--   * planos.id_producto, ordenes_produccion.id_producto, pedido_detalles.id_producto:
--     FK opcionales a productos. pedido_detalles.codigo_producto se mantiene como texto.
--     Sin relleno automático: las OP sin producto quedan bloqueadas para liberación.
--   * El plano pertenece al producto: planos.id_proyecto pasa a opcional (ON DELETE SET NULL),
--     planos.codigo_op pasa a opcional sin DEFAULT y planos.archivo_url (si existe) a opcional.
-- Idempotente y sin pérdida de datos. Cada cambio comprueba antes lo que existe, porque el
-- esquema de sgi_db puede no coincidir con el de los modelos.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Reversión: 18_REVERSION_PRODUCTOS_RN.sql

BEGIN;

CREATE TABLE IF NOT EXISTS productos (
    id_producto UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_rn VARCHAR(17) NOT NULL,
    codigo_anterior VARCHAR(50) NULL,
    descripcion VARCHAR(255) NOT NULL,
    familia VARCHAR(100) NULL,
    subfamilia VARCHAR(100) NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
    id_articulo UUID NULL REFERENCES articulos_inventario(id_articulo) ON DELETE SET NULL,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_productos_codigo_rn UNIQUE (codigo_rn),
    CONSTRAINT ck_productos_codigo_rn CHECK (codigo_rn ~ '^RN-[0-9]{3}-[0-9]{3}-[0-9]{6}$'),
    CONSTRAINT ck_productos_estado CHECK (estado IN ('ACTIVO', 'OBSOLETO'))
);
CREATE INDEX IF NOT EXISTS ix_productos_codigo_anterior ON productos (codigo_anterior);

ALTER TABLE planos ADD COLUMN IF NOT EXISTS id_producto UUID NULL;
ALTER TABLE ordenes_produccion ADD COLUMN IF NOT EXISTS id_producto UUID NULL;
ALTER TABLE pedido_detalles ADD COLUMN IF NOT EXISTS id_producto UUID NULL;

DO $$
DECLARE
    tabla TEXT;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['planos', 'ordenes_produccion', 'pedido_detalles'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = tabla::regclass AND conname = 'fk_' || tabla || '_id_producto'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE RESTRICT',
                tabla, 'fk_' || tabla || '_id_producto'
            );
        END IF;
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (id_producto)', 'ix_' || tabla || '_id_producto', tabla);
    END LOOP;
END $$;

-- planos.id_proyecto: opcional y ON DELETE SET NULL (el plano pertenece al producto)
DO $$
DECLARE
    restriccion TEXT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'id_proyecto'
    ) THEN
        ALTER TABLE planos ALTER COLUMN id_proyecto DROP NOT NULL;
        FOR restriccion IN
            SELECT c.conname FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.conrelid = 'planos'::regclass AND c.contype = 'f'
              AND c.confrelid = 'proyectos'::regclass AND a.attname = 'id_proyecto'
              AND c.conname <> 'fk_planos_id_proyecto'
        LOOP
            EXECUTE format('ALTER TABLE planos DROP CONSTRAINT %I', restriccion);
        END LOOP;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conrelid = 'planos'::regclass AND conname = 'fk_planos_id_proyecto'
        ) THEN
            ALTER TABLE planos ADD CONSTRAINT fk_planos_id_proyecto
                FOREIGN KEY (id_proyecto) REFERENCES proyectos(id_proyecto) ON DELETE SET NULL;
        END IF;
    END IF;
END $$;

-- planos.codigo_op: opcional y sin DEFAULT '4007256'
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'codigo_op'
    ) THEN
        ALTER TABLE planos ALTER COLUMN codigo_op DROP NOT NULL;
        ALTER TABLE planos ALTER COLUMN codigo_op DROP DEFAULT;
    END IF;
END $$;

-- planos.archivo_url (columna física del esquema heredado): opcional
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'planos' AND column_name = 'archivo_url'
    ) THEN
        ALTER TABLE planos ALTER COLUMN archivo_url DROP NOT NULL;
    END IF;
END $$;

COMMIT;
