-- 31_REVERSION_CONFIGURACION_ROLES.sql
-- Reversión de 31_MIGRACION_CONFIGURACION_ROLES.sql.
--   * Borra solo lo que la migración registró en migracion_31_registro: la asignación a ADMIN,
--     PERM_CONFIGURACION_ROLES y la tabla rol_permisos_historial.
--   * Se detiene SIN cambiar nada si rol_permisos_historial tiene cambios registrados (es el
--     registro de quién cambió permisos y cuándo: respáldelo y vacíelo antes) o si hay
--     asignaciones posteriores de PERM_CONFIGURACION_ROLES.
--   * Los roles creados y los permisos asignados desde la pantalla se conservan.
--   * Elimina migracion_31_registro. Sin esa tabla no hay nada que revertir.
-- Al revertir, la pantalla de Configuración de roles responde 403 a todos hasta reaplicarla.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_cambios      bigint;
    v_asignaciones text;
BEGIN
    IF to_regclass('public.migracion_31_registro') IS NULL THEN
        RAISE NOTICE 'No existe migracion_31_registro: la migración 31 no está aplicada.';
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM migracion_31_registro WHERE tipo = 'TABLA')
       AND to_regclass('public.rol_permisos_historial') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM rol_permisos_historial' INTO v_cambios;
        IF v_cambios > 0 THEN
            RAISE EXCEPTION 'rol_permisos_historial tiene % cambios registrados; respáldelos y vacíe la tabla antes de revertir.', v_cambios;
        END IF;
    END IF;

    SELECT string_agg(rp.id_rol, ', ' ORDER BY rp.id_rol) INTO v_asignaciones
      FROM rol_permisos rp
     WHERE EXISTS (SELECT 1 FROM migracion_31_registro r WHERE r.tipo = 'PERMISO' AND r.id_permiso = rp.id_permiso)
       AND NOT EXISTS (
            SELECT 1 FROM migracion_31_registro r
             WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso
     );
    IF v_asignaciones IS NOT NULL THEN
        RAISE EXCEPTION 'Asignaciones posteriores de PERM_CONFIGURACION_ROLES: %', v_asignaciones;
    END IF;

    DELETE FROM rol_permisos rp
     USING migracion_31_registro r
     WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso;
    DELETE FROM permisos p
     USING migracion_31_registro r
     WHERE r.tipo = 'PERMISO' AND r.id_permiso = p.id_permiso;
    IF EXISTS (SELECT 1 FROM migracion_31_registro WHERE tipo = 'TABLA') THEN
        DROP TABLE IF EXISTS public.rol_permisos_historial;
    END IF;

    DROP TABLE public.migracion_31_registro;
END $$;

COMMIT;
