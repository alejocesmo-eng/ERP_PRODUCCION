-- 28_MIGRACION_OP_UNIDAD_ACTUAL.sql
-- Unidad actual de la OP y traslado obligatorio (reglas/permisos-por-rol-modulo.md del proyecto
-- PRISMA; lógica en app/services/unidad_op.py):
--   * ordenes_produccion.unidad_actual: MECANIZADOS, SERVICIOS, METALISTERIA, TERCERO, DESPACHO o
--     SIN_ASIGNAR (por defecto).
--   * op_traslados_unidad: quién (correo y rol), cuándo y de qué unidad a cuál. Solo se agregan filas.
--   * Las OP existentes toman la unidad del proceso en el que están; solo se tocan las que siguen en
--     SIN_ASIGNAR, así que volver a aplicarla no deshace traslados:
--       1. TERMINADA, INSPECCION_CALIDAD o EN_INSPECCION cuya última inspección es
--          APROBADO_TRATAMIENTO: TERCERO (piezas enviadas a tratamiento).
--       2. LISTA_PARA_LIBERAR cuya última inspección es APROBADO_DESPACHO, y CERRADA: DESPACHO.
--       3. Liberadas, en producción o en inspección: la unidad de su plano (id_plano) o, sin plano,
--          la única unidad de los planos vigentes de su producto (Mecanizados, Servicios o
--          Metalistería, sin distinguir tildes ni mayúsculas).
--       4. El resto queda SIN_ASIGNAR: no ha llegado a una unidad (BORRADOR, EN_REVISION_CALIDAD,
--          APROBADA, PENDIENTE_MATERIAL, CANCELADA) o no se puede deducir (sin plano, planos de
--          varias unidades o LISTA_PARA_LIBERAR sin aprobación de despacho).
--     La deducción no crea filas en op_traslados_unidad.
--   * Al final avisa (NOTICE) cuántas OP quedaron SIN_ASIGNAR. Para listarlas:
--       SELECT codigo_op, estado FROM ordenes_produccion WHERE unidad_actual = 'SIN_ASIGNAR' ORDER BY codigo_op;
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Reversión: 28_REVERSION_OP_UNIDAD_ACTUAL.sql

BEGIN;

ALTER TABLE ordenes_produccion
    ADD COLUMN IF NOT EXISTS unidad_actual VARCHAR(20) NOT NULL DEFAULT 'SIN_ASIGNAR';
ALTER TABLE ordenes_produccion DROP CONSTRAINT IF EXISTS ck_ordenes_produccion_unidad_actual;
ALTER TABLE ordenes_produccion ADD CONSTRAINT ck_ordenes_produccion_unidad_actual
    CHECK (unidad_actual IN ('MECANIZADOS', 'SERVICIOS', 'METALISTERIA', 'TERCERO', 'DESPACHO', 'SIN_ASIGNAR'));
COMMENT ON COLUMN ordenes_produccion.unidad_actual IS
    'Unidad donde está la OP; cambia solo con un traslado (op_traslados_unidad). Migración 28.';

CREATE TABLE IF NOT EXISTS op_traslados_unidad (
    id_traslado    UUID PRIMARY KEY,
    id_op          UUID NOT NULL REFERENCES ordenes_produccion(id_op) ON DELETE RESTRICT,
    unidad_origen  VARCHAR(20) NOT NULL,
    unidad_destino VARCHAR(20) NOT NULL,
    usuario_email  VARCHAR(150) NOT NULL,
    rol            VARCHAR(50),
    observacion    TEXT,
    registrado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_op_traslados_unidad_origen
        CHECK (unidad_origen IN ('MECANIZADOS', 'SERVICIOS', 'METALISTERIA', 'TERCERO', 'DESPACHO', 'SIN_ASIGNAR')),
    CONSTRAINT ck_op_traslados_unidad_destino
        CHECK (unidad_destino IN ('MECANIZADOS', 'SERVICIOS', 'METALISTERIA', 'TERCERO', 'DESPACHO')),
    CONSTRAINT ck_op_traslados_unidad_distinta CHECK (unidad_origen <> unidad_destino)
);
CREATE INDEX IF NOT EXISTS ix_op_traslados_unidad_id_op ON op_traslados_unidad (id_op);
COMMENT ON TABLE op_traslados_unidad IS
    'Traslados de la OP entre unidades: quién, cuándo y de qué unidad a cuál. Migración 28.';

-- Unidad de proceso de un texto de planos.unidad_planta (NULL si no se reconoce)
CREATE OR REPLACE FUNCTION pg_temp.unidad_de_proceso(texto TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE lower(translate(trim(coalesce(texto, '')), 'áéíóúÁÉÍÓÚ', 'aeiouAEIOU'))
        WHEN 'mecanizados' THEN 'MECANIZADOS'
        WHEN 'servicios' THEN 'SERVICIOS'
        WHEN 'metalisteria' THEN 'METALISTERIA'
    END
$$;

DO $$
DECLARE
    v_sin_asignar integer;
BEGIN
    -- 1 y 2: según la última inspección de calidad (si la tabla existe)
    IF to_regclass('public.inspecciones_calidad') IS NOT NULL THEN
        WITH ultima AS (
            SELECT DISTINCT ON (codigo_op) codigo_op, resultado_inspeccion
              FROM inspecciones_calidad
             ORDER BY codigo_op, fecha_inspeccion DESC NULLS LAST
        )
        UPDATE ordenes_produccion op
           SET unidad_actual = CASE
                   WHEN op.estado::text IN ('TERMINADA', 'INSPECCION_CALIDAD', 'EN_INSPECCION')
                        AND u.resultado_inspeccion = 'APROBADO_TRATAMIENTO' THEN 'TERCERO'
                   WHEN op.estado::text = 'LISTA_PARA_LIBERAR'
                        AND u.resultado_inspeccion = 'APROBADO_DESPACHO' THEN 'DESPACHO'
               END
          FROM ultima u
         WHERE u.codigo_op = op.codigo_op
           AND op.unidad_actual = 'SIN_ASIGNAR'
           AND (
                (op.estado::text IN ('TERMINADA', 'INSPECCION_CALIDAD', 'EN_INSPECCION')
                 AND u.resultado_inspeccion = 'APROBADO_TRATAMIENTO')
             OR (op.estado::text = 'LISTA_PARA_LIBERAR' AND u.resultado_inspeccion = 'APROBADO_DESPACHO')
           );
    END IF;

    UPDATE ordenes_produccion SET unidad_actual = 'DESPACHO'
     WHERE unidad_actual = 'SIN_ASIGNAR' AND estado::text = 'CERRADA';

    -- 3: unidad del plano de la OP o, sin plano, la única de los planos vigentes del producto
    WITH por_producto AS (
        SELECT p.id_producto, min(pg_temp.unidad_de_proceso(p.unidad_planta)) AS unidad
          FROM planos p
         WHERE p.id_producto IS NOT NULL
           AND (p.estado IS NULL OR p.estado::text <> 'OBSOLETO')
         GROUP BY p.id_producto
        HAVING count(DISTINCT coalesce(pg_temp.unidad_de_proceso(p.unidad_planta), '?')) = 1
    ), deducida AS (
        SELECT op.id_op,
               coalesce(pg_temp.unidad_de_proceso(pl.unidad_planta),
                        CASE WHEN op.id_plano IS NULL THEN pp.unidad END) AS unidad
          FROM ordenes_produccion op
          LEFT JOIN planos pl ON pl.id_plano = op.id_plano
          LEFT JOIN por_producto pp ON pp.id_producto = op.id_producto
         WHERE op.unidad_actual = 'SIN_ASIGNAR'
           AND op.estado::text IN ('LIBERADA', 'LIBERADA_PRODUCCION', 'EN_PRODUCCION', 'EN_PROCESO_CNC',
                                   'EN_SETUP', 'MECANIZADO', 'TERMINADA', 'INSPECCION_CALIDAD', 'EN_INSPECCION')
    )
    UPDATE ordenes_produccion op SET unidad_actual = d.unidad
      FROM deducida d
     WHERE d.id_op = op.id_op AND d.unidad IS NOT NULL;

    SELECT count(*) INTO v_sin_asignar FROM ordenes_produccion WHERE unidad_actual = 'SIN_ASIGNAR';
    RAISE NOTICE 'OP en SIN_ASIGNAR tras la migración 28: %', v_sin_asignar;
END $$;

COMMIT;
