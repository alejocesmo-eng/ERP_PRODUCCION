-- 36_MIGRACION_PEDIDO_CERRADO.sql
-- Estado CERRADO del pedido y aviso de cierre de OP por respaldo (decisión de Alejo, 2026-11-18;
-- Regla 6 de reglas/pedido-cotizacion-cambios.md y reglas/cierre-op-seguro.md).
--   * Tipo estado_proyecto con CERRADO: el Jefe de Producción cierra el pedido a mano cuando todas
--     sus OP están cerradas. Un pedido CERRADO queda como histórico, sin edición.
--   * proyectos.estado (estado_proyecto, NOT NULL, por defecto BORRADOR). Si la columna no existe se
--     crea y se llena desde confirmado: CONFIRMADO si el pedido está confirmado, BORRADOR si no.
--   * tiponotificacionenum con OP_CERRADA_RESPALDO: aviso al Jefe cuando un líder de respaldo cierra
--     una OP.
-- Se detiene sin cambiar nada si proyectos.estado existe con otro tipo (esquema anterior): revisar a
-- mano. Las marcas "migración 36" en los comentarios del tipo y de la columna le dicen a la reversión
-- qué creó esta migración.
-- Requiere PostgreSQL 12 o superior (ALTER TYPE ... ADD VALUE dentro de una transacción). El valor
-- nuevo no se usa en esta misma transacción.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Reversión: 36_REVERSION_PEDIDO_CERRADO.sql

BEGIN;

DO $$
DECLARE
    v_tipo text;
BEGIN
    SELECT udt_name INTO v_tipo FROM information_schema.columns
     WHERE table_schema = current_schema() AND table_name = 'proyectos' AND column_name = 'estado';
    IF v_tipo IS NOT NULL AND v_tipo <> 'estado_proyecto' THEN
        RAISE EXCEPTION 'proyectos.estado existe con tipo %; se esperaba estado_proyecto. Revise el esquema antes de migrar.', v_tipo;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'estado_proyecto') THEN
        CREATE TYPE estado_proyecto AS ENUM ('BORRADOR', 'CONFIRMADO', 'EN_DISENO', 'FINALIZADO', 'CANCELADO', 'CERRADO');
        COMMENT ON TYPE estado_proyecto IS 'Estados del pedido. Creado por la migración 36.';
    ELSE
        ALTER TYPE estado_proyecto ADD VALUE IF NOT EXISTS 'CERRADO';
    END IF;

    IF v_tipo IS NULL THEN
        ALTER TABLE proyectos ADD COLUMN estado estado_proyecto;
        UPDATE proyectos SET estado = CASE WHEN confirmado THEN 'CONFIRMADO'::estado_proyecto
                                           ELSE 'BORRADOR'::estado_proyecto END;
        COMMENT ON COLUMN proyectos.estado IS
            'Estado del pedido; CERRADO lo deja como histórico sin edición. Creada por la migración 36.';
    ELSE
        UPDATE proyectos SET estado = CASE WHEN confirmado THEN 'CONFIRMADO'::estado_proyecto
                                           ELSE 'BORRADOR'::estado_proyecto END
         WHERE estado IS NULL;
    END IF;
    ALTER TABLE proyectos ALTER COLUMN estado SET DEFAULT 'BORRADOR';
    ALTER TABLE proyectos ALTER COLUMN estado SET NOT NULL;

    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tiponotificacionenum') THEN
        ALTER TYPE tiponotificacionenum ADD VALUE IF NOT EXISTS 'OP_CERRADA_RESPALDO';
    END IF;
END $$;

COMMIT;
