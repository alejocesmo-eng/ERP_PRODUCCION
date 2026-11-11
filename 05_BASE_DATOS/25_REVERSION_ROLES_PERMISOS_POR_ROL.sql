-- 25_REVERSION_ROLES_PERMISOS_POR_ROL.sql
-- Reversión de 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql.
--   * Borra solo lo que la migración registró en migracion_25_registro: asignaciones, permisos
--     y roles. Los roles y asignaciones que ya existían (por ejemplo OPERARIO y MANTENIMIENTO de
--     cargar_semilla.py, o PERM_PROYECTO_CREAR de VENTAS) se conservan.
--   * Devuelve PERM_OP_LIBERAR a los roles que lo tenían antes (DISENO por la migración 16).
--   * Se detiene SIN cambiar nada si algún usuario tiene un rol creado por la migración o si hay
--     asignaciones posteriores sobre esos roles o permisos: lista los casos para reasignarlos.
--   * Elimina migracion_25_registro. Sin esa tabla no hay nada que revertir.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_usuarios     text;
    v_asignaciones text;
BEGIN
    IF to_regclass('public.migracion_25_registro') IS NULL THEN
        RAISE NOTICE 'No existe migracion_25_registro: la migración 25 no está aplicada.';
        RETURN;
    END IF;

    SELECT string_agg(u.email || ' (' || u.id_rol || ')', ', ' ORDER BY u.id_rol, u.email)
      INTO v_usuarios
      FROM usuarios u
      JOIN migracion_25_registro r ON r.tipo = 'ROL' AND r.id_rol = u.id_rol;
    IF v_usuarios IS NOT NULL THEN
        RAISE EXCEPTION 'Usuarios con roles de la migración 25; reasígnelos antes de revertir: %', v_usuarios;
    END IF;

    SELECT string_agg(rp.id_rol || '/' || rp.id_permiso, ', ' ORDER BY rp.id_rol, rp.id_permiso)
      INTO v_asignaciones
      FROM rol_permisos rp
     WHERE (
            EXISTS (SELECT 1 FROM migracion_25_registro r WHERE r.tipo = 'ROL' AND r.id_rol = rp.id_rol)
         OR EXISTS (SELECT 1 FROM migracion_25_registro r WHERE r.tipo = 'PERMISO' AND r.id_permiso = rp.id_permiso)
     )
       AND NOT EXISTS (
            SELECT 1 FROM migracion_25_registro r
             WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso
     );
    IF v_asignaciones IS NOT NULL THEN
        RAISE EXCEPTION 'Asignaciones posteriores a la migración 25 sobre sus roles o permisos: %', v_asignaciones;
    END IF;

    DELETE FROM rol_permisos rp
     USING migracion_25_registro r
     WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso;

    INSERT INTO rol_permisos (id_rol, id_permiso)
    SELECT r.id_rol, r.id_permiso
      FROM migracion_25_registro r
     WHERE r.tipo = 'ROL_PERMISO_RETIRADO'
       AND EXISTS (SELECT 1 FROM roles ro WHERE ro.id_rol = r.id_rol)
       AND EXISTS (SELECT 1 FROM permisos p WHERE p.id_permiso = r.id_permiso)
    ON CONFLICT DO NOTHING;

    DELETE FROM permisos p
     USING migracion_25_registro r
     WHERE r.tipo = 'PERMISO' AND r.id_permiso = p.id_permiso;

    DELETE FROM roles ro
     USING migracion_25_registro r
     WHERE r.tipo = 'ROL' AND r.id_rol = ro.id_rol;

    DROP TABLE public.migracion_25_registro;
END $$;

COMMIT;
