-- 32_REVERSION_ROL_LIDER_SERVICIOS.sql
-- Reversión de 32_MIGRACION_ROL_LIDER_SERVICIOS.sql.
--   * Borra solo lo que la migración registró en migracion_32_registro: asignaciones y rol.
--   * Se detiene SIN cambiar nada si algún usuario tiene LIDER_SERVICIOS (creado por la migración)
--     o si el rol tiene asignaciones posteriores (por ejemplo, desde Configuración de roles):
--     lista los casos.
--   * Elimina migracion_32_registro. Sin esa tabla no hay nada que revertir.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_usuarios     text;
    v_asignaciones text;
BEGIN
    IF to_regclass('public.migracion_32_registro') IS NULL THEN
        RAISE NOTICE 'No existe migracion_32_registro: la migración 32 no está aplicada.';
        RETURN;
    END IF;

    SELECT string_agg(u.email, ', ' ORDER BY u.email) INTO v_usuarios
      FROM usuarios u
      JOIN migracion_32_registro r ON r.tipo = 'ROL' AND r.id_rol = u.id_rol;
    IF v_usuarios IS NOT NULL THEN
        RAISE EXCEPTION 'Usuarios con LIDER_SERVICIOS; reasígnelos antes de revertir: %', v_usuarios;
    END IF;

    SELECT string_agg(rp.id_rol || '/' || rp.id_permiso, ', ' ORDER BY rp.id_permiso) INTO v_asignaciones
      FROM rol_permisos rp
     WHERE EXISTS (SELECT 1 FROM migracion_32_registro r WHERE r.tipo = 'ROL' AND r.id_rol = rp.id_rol)
       AND NOT EXISTS (
            SELECT 1 FROM migracion_32_registro r
             WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso
     );
    IF v_asignaciones IS NOT NULL THEN
        RAISE EXCEPTION 'Asignaciones posteriores a la migración 32: %', v_asignaciones;
    END IF;

    DELETE FROM rol_permisos rp
     USING migracion_32_registro r
     WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso;
    DELETE FROM roles ro
     USING migracion_32_registro r
     WHERE r.tipo = 'ROL' AND r.id_rol = ro.id_rol;

    DROP TABLE public.migracion_32_registro;
END $$;

COMMIT;
