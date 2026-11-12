-- 29_REVERSION_ROL_CAPTURISTA_TIEMPOS.sql
-- Reversión de 29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql.
--   * Borra solo lo que la migración registró en migracion_29_registro: asignaciones, permiso y rol.
--   * Se detiene SIN cambiar nada si algún usuario tiene CAPTURISTA_TIEMPOS (creado por la
--     migración) o si hay asignaciones posteriores de PERM_TIEMPOS_REGISTRAR: lista los casos.
--   * Elimina migracion_29_registro. Sin esa tabla no hay nada que revertir.
-- Al revertir, las rutas de tiempos rechazan a todos los roles hasta reaplicarla.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_usuarios     text;
    v_asignaciones text;
BEGIN
    IF to_regclass('public.migracion_29_registro') IS NULL THEN
        RAISE NOTICE 'No existe migracion_29_registro: la migración 29 no está aplicada.';
        RETURN;
    END IF;

    SELECT string_agg(u.email, ', ' ORDER BY u.email) INTO v_usuarios
      FROM usuarios u
      JOIN migracion_29_registro r ON r.tipo = 'ROL' AND r.id_rol = u.id_rol;
    IF v_usuarios IS NOT NULL THEN
        RAISE EXCEPTION 'Usuarios con CAPTURISTA_TIEMPOS; reasígnelos antes de revertir: %', v_usuarios;
    END IF;

    SELECT string_agg(rp.id_rol || '/' || rp.id_permiso, ', ' ORDER BY rp.id_rol) INTO v_asignaciones
      FROM rol_permisos rp
     WHERE (
            EXISTS (SELECT 1 FROM migracion_29_registro r WHERE r.tipo = 'ROL' AND r.id_rol = rp.id_rol)
         OR EXISTS (SELECT 1 FROM migracion_29_registro r WHERE r.tipo = 'PERMISO' AND r.id_permiso = rp.id_permiso)
     )
       AND NOT EXISTS (
            SELECT 1 FROM migracion_29_registro r
             WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso
     );
    IF v_asignaciones IS NOT NULL THEN
        RAISE EXCEPTION 'Asignaciones posteriores a la migración 29: %', v_asignaciones;
    END IF;

    DELETE FROM rol_permisos rp
     USING migracion_29_registro r
     WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso;
    DELETE FROM permisos p
     USING migracion_29_registro r
     WHERE r.tipo = 'PERMISO' AND r.id_permiso = p.id_permiso;
    DELETE FROM roles ro
     USING migracion_29_registro r
     WHERE r.tipo = 'ROL' AND r.id_rol = ro.id_rol;

    DROP TABLE public.migracion_29_registro;
END $$;

COMMIT;
