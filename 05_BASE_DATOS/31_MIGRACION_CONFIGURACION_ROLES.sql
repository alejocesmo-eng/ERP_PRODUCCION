-- 31_MIGRACION_CONFIGURACION_ROLES.sql
-- Pantalla de Configuración de roles y permisos (app/api/v1/configuracion_roles.py).
--   * rol_permisos_historial: cada permiso asignado o retirado desde la pantalla, con el correo
--     de quien lo cambió y la fecha. Sin claves foráneas: el registro se conserva aunque el rol
--     se elimine.
--   * PERM_CONFIGURACION_ROLES: permiso técnico de acceso a la pantalla. Solo entra ADMIN (rol
--     leído de la base) y solo si su rol tiene este permiso; la pantalla no deja que ADMIN se lo
--     quite a sí mismo. Se asigna a ADMIN.
--   * No crea roles ni asigna permisos de negocio: esos se configuran en el arranque.
--   * Registra en migracion_31_registro lo que inserta, para que la reversión deshaga eso y nada más.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Requiere 15_MIGRACION_ROL_PERMISOS.sql y el rol ADMIN.
-- Reversión: 31_REVERSION_CONFIGURACION_ROLES.sql

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM roles WHERE id_rol = 'ADMIN') THEN
        RAISE EXCEPTION 'Falta el rol ADMIN de 02_DATOS_INICIALES.sql.';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS migracion_31_registro (
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('TABLA', 'PERMISO', 'ROL_PERMISO')),
    id_rol VARCHAR(50),
    id_permiso VARCHAR(100),
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE migracion_31_registro IS
    'Filas insertadas por 31_MIGRACION_CONFIGURACION_ROLES.sql; la usa su reversión.';

INSERT INTO migracion_31_registro (tipo)
SELECT 'TABLA' WHERE to_regclass('public.rol_permisos_historial') IS NULL;

CREATE TABLE IF NOT EXISTS rol_permisos_historial (
    id SERIAL PRIMARY KEY,
    id_rol VARCHAR(50) NOT NULL,
    id_permiso VARCHAR(100) NOT NULL,
    accion VARCHAR(10) NOT NULL CHECK (accion IN ('ASIGNADO', 'RETIRADO')),
    usuario_email VARCHAR(100) NOT NULL,
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_rol_permisos_historial_id_rol ON rol_permisos_historial (id_rol);
COMMENT ON TABLE rol_permisos_historial IS
    'Permisos asignados o retirados desde Configuración: quién (usuario_email) y cuándo.';

WITH nuevo AS (
    INSERT INTO permisos (id_permiso, modulo, descripcion)
    VALUES ('PERM_CONFIGURACION_ROLES', 'ADMIN', 'Acceso a Configuración de roles y permisos')
    ON CONFLICT (id_permiso) DO NOTHING
    RETURNING id_permiso
)
INSERT INTO migracion_31_registro (tipo, id_permiso) SELECT 'PERMISO', id_permiso FROM nuevo;

WITH nueva AS (
    INSERT INTO rol_permisos (id_rol, id_permiso)
    VALUES ('ADMIN', 'PERM_CONFIGURACION_ROLES')
    ON CONFLICT DO NOTHING
    RETURNING id_rol, id_permiso
)
INSERT INTO migracion_31_registro (tipo, id_rol, id_permiso)
SELECT 'ROL_PERMISO', id_rol, id_permiso FROM nueva;

COMMIT;
