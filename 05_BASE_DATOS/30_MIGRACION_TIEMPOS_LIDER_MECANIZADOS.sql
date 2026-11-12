-- 30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql
-- LIDER_MECANIZADOS vuelve a registrar tiempos (setup, mecanizado, pausa y cierre de sublote):
-- recibe PERM_TIEMPOS_REGISTRAR, que la migración 29 dio solo a OPERARIO, CAPTURISTA_TIEMPOS,
-- JEFE_PRODUCCION y ADMIN (corrección de Alejo, 2026-11-12). Sigue sin PERM_OP_LIBERAR,
-- PERM_RETENCION_GESTIONAR, PERM_EXPEDIENTE_COSTOS_VER ni PERM_VALOR_COTIZADO_VER.
--   * Registra en migracion_30_registro la asignación que inserta, para que la reversión la quite
--     solo si la puso esta migración.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Requiere 27_MIGRACION_ROL_LIDER_MECANIZADOS.sql y 29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql.
-- Reversión: 30_REVERSION_TIEMPOS_LIDER_MECANIZADOS.sql

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM roles WHERE id_rol = 'LIDER_MECANIZADOS') THEN
        RAISE EXCEPTION 'Falta el rol LIDER_MECANIZADOS: aplique antes la migración 27.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM permisos WHERE id_permiso = 'PERM_TIEMPOS_REGISTRAR') THEN
        RAISE EXCEPTION 'Falta el permiso PERM_TIEMPOS_REGISTRAR: aplique antes la migración 29.';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS migracion_30_registro (
    id_rol VARCHAR(50) NOT NULL,
    id_permiso VARCHAR(100) NOT NULL,
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE migracion_30_registro IS
    'Asignación insertada por 30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql; la usa su reversión.';

WITH nuevas AS (
    INSERT INTO rol_permisos (id_rol, id_permiso) VALUES ('LIDER_MECANIZADOS', 'PERM_TIEMPOS_REGISTRAR')
    ON CONFLICT DO NOTHING
    RETURNING id_rol, id_permiso
)
INSERT INTO migracion_30_registro (id_rol, id_permiso) SELECT id_rol, id_permiso FROM nuevas;

COMMIT;
