-- 29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql
-- Rol CAPTURISTA_TIEMPOS, "Capturista de tiempos": carga manual de tiempos de operaciones de OP
-- en cualquier unidad (Mecanizados, Servicios, Metalistería).
--   * El catálogo no tenía permiso para registrar tiempos (OPERARIO no tenía filas en
--     rol_permisos y las rutas solo pedían token). Se crea PERM_TIEMPOS_REGISTRAR (decisión de
--     Alejo, 2026-11-12) y lo exigen las rutas de setup, mecanizado, pausa y cierre de sublote.
--   * PERM_TIEMPOS_REGISTRAR: OPERARIO, CAPTURISTA_TIEMPOS, JEFE_PRODUCCION y ADMIN.
--   * CAPTURISTA_TIEMPOS solo tiene ese permiso: sin costos, valor cotizado, cliente, planos ni
--     cambios de unidad, liberación, cierre o retención (la aplicación le cierra las demás rutas).
--   * Registra en migracion_29_registro lo que inserta, para que la reversión deshaga eso y nada más.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Requiere 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql (OPERARIO y JEFE_PRODUCCION).
-- Reversión: 29_REVERSION_ROL_CAPTURISTA_TIEMPOS.sql

BEGIN;

DO $$
DECLARE
    v_faltantes text;
BEGIN
    SELECT string_agg(r, ', ' ORDER BY r) INTO v_faltantes
      FROM unnest(ARRAY['ADMIN', 'OPERARIO', 'JEFE_PRODUCCION']) AS r
     WHERE NOT EXISTS (SELECT 1 FROM roles WHERE id_rol = r);
    IF v_faltantes IS NOT NULL THEN
        RAISE EXCEPTION 'Faltan roles (aplique antes la migración 25): %', v_faltantes;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS migracion_29_registro (
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('ROL', 'PERMISO', 'ROL_PERMISO')),
    id_rol VARCHAR(50),
    id_permiso VARCHAR(100),
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE migracion_29_registro IS
    'Filas insertadas por 29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql; la usa su reversión.';

WITH nuevo AS (
    INSERT INTO roles (id_rol, nombre_rol, descripcion)
    VALUES ('CAPTURISTA_TIEMPOS', 'Capturista de tiempos',
            'Carga manual de tiempos de operaciones de OP en cualquier unidad; nada más')
    ON CONFLICT (id_rol) DO NOTHING
    RETURNING id_rol
)
INSERT INTO migracion_29_registro (tipo, id_rol) SELECT 'ROL', id_rol FROM nuevo;

WITH nuevo AS (
    INSERT INTO permisos (id_permiso, modulo, descripcion)
    VALUES ('PERM_TIEMPOS_REGISTRAR', 'PRODUCCION', 'Registrar tiempos de operaciones de OP')
    ON CONFLICT (id_permiso) DO NOTHING
    RETURNING id_permiso
)
INSERT INTO migracion_29_registro (tipo, id_permiso) SELECT 'PERMISO', id_permiso FROM nuevo;

WITH nuevas AS (
    INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
    ('OPERARIO', 'PERM_TIEMPOS_REGISTRAR'),
    ('CAPTURISTA_TIEMPOS', 'PERM_TIEMPOS_REGISTRAR'),
    ('JEFE_PRODUCCION', 'PERM_TIEMPOS_REGISTRAR'),
    ('ADMIN', 'PERM_TIEMPOS_REGISTRAR')
    ON CONFLICT DO NOTHING
    RETURNING id_rol, id_permiso
)
INSERT INTO migracion_29_registro (tipo, id_rol, id_permiso)
SELECT 'ROL_PERMISO', id_rol, id_permiso FROM nuevas;

COMMIT;
