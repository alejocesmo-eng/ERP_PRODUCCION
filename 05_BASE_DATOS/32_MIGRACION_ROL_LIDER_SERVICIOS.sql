-- 32_MIGRACION_ROL_LIDER_SERVICIOS.sql
-- Rol LIDER_SERVICIOS, "Líder de Servicios" (reglas/permisos-por-rol-modulo.md del proyecto PRISMA).
--   * Ve solo las OP de su área (Servicios), con datos técnicos desde que se crean, e información
--     e histórico del cliente. Sin costos ni valor cotizado: no recibe PERM_EXPEDIENTE_COSTOS_VER ni
--     PERM_VALOR_COTIZADO_VER. Tampoco libera (PERM_OP_LIBERAR) ni retiene (PERM_RETENCION_GESTIONAR).
--   * PERM_OP_CERRAR: cierra OP solo de su área, como respaldo del Jefe de Producción (la
--     aplicación restringe el cierre a su área).
--   * PERM_TIEMPOS_REGISTRAR (migración 29, no se crea otro): registro de avance y tiempos. Es la
--     asignación inicial; ADMIN la cambia desde Configuración de roles (migración 31).
--   * Cambia la unidad de las OP que están en Servicios (la aplicación lo decide por rol).
--   * Registra en migracion_32_registro lo que inserta, para que la reversión deshaga eso y nada más.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Requiere 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql (PERM_OP_CERRAR) y
-- 29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql (PERM_TIEMPOS_REGISTRAR).
-- Reversión: 32_REVERSION_ROL_LIDER_SERVICIOS.sql

BEGIN;

DO $$
DECLARE
    v_faltantes text;
BEGIN
    SELECT string_agg(p, ', ' ORDER BY p) INTO v_faltantes
      FROM unnest(ARRAY['PERM_OP_CERRAR', 'PERM_TIEMPOS_REGISTRAR']) AS p
     WHERE NOT EXISTS (SELECT 1 FROM permisos WHERE id_permiso = p);
    IF v_faltantes IS NOT NULL THEN
        RAISE EXCEPTION 'Faltan permisos (aplique antes las migraciones 25 y 29): %', v_faltantes;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS migracion_32_registro (
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('ROL', 'ROL_PERMISO')),
    id_rol VARCHAR(50),
    id_permiso VARCHAR(100),
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE migracion_32_registro IS
    'Filas insertadas por 32_MIGRACION_ROL_LIDER_SERVICIOS.sql; la usa su reversión.';

WITH nuevo AS (
    INSERT INTO roles (id_rol, nombre_rol, descripcion)
    VALUES ('LIDER_SERVICIOS', 'Líder de Servicios',
            'OP de Servicios desde que se crean; avance y tiempos; cierra OP de su área como respaldo; sin costos')
    ON CONFLICT (id_rol) DO NOTHING
    RETURNING id_rol
)
INSERT INTO migracion_32_registro (tipo, id_rol) SELECT 'ROL', id_rol FROM nuevo;

WITH nuevas AS (
    INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
    ('LIDER_SERVICIOS', 'PERM_OP_CERRAR'),
    ('LIDER_SERVICIOS', 'PERM_TIEMPOS_REGISTRAR')
    ON CONFLICT DO NOTHING
    RETURNING id_rol, id_permiso
)
INSERT INTO migracion_32_registro (tipo, id_rol, id_permiso)
SELECT 'ROL_PERMISO', id_rol, id_permiso FROM nuevas;

COMMIT;
