-- 27_REVERSION_ROL_LIDER_MECANIZADOS.sql
-- Reversión de 27_MIGRACION_ROL_LIDER_MECANIZADOS.sql.
--   * Quita PERM_OP_CERRAR de LIDER_MECANIZADOS si lo asignó la migración.
--   * Si la migración renombró el rol, crea otra vez LIDER_PRODUCCION con el nombre y la
--     descripción de la migración 25, le pasa los usuarios y las asignaciones de
--     LIDER_MECANIZADOS (también los asignados después) y borra LIDER_MECANIZADOS.
--     migracion_25_registro vuelve a nombrar LIDER_PRODUCCION.
--   * Elimina migracion_27_registro. Sin esa tabla no hay nada que revertir.
-- Revierta la 27 antes que la 25. Idempotente. Solo con autorización de Dirección y respaldo
-- previo. NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.migracion_27_registro') IS NULL THEN
        RAISE NOTICE 'No existe migracion_27_registro: la migración 27 no está aplicada.';
        RETURN;
    END IF;

    DELETE FROM rol_permisos rp
     USING migracion_27_registro r
     WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso;

    IF EXISTS (SELECT 1 FROM migracion_27_registro WHERE tipo = 'ROL_RENOMBRADO') THEN
        INSERT INTO roles (id_rol, nombre_rol, descripcion)
        VALUES ('LIDER_PRODUCCION', 'Líder de producción', 'Avance de operaciones de su área, sin costos')
        ON CONFLICT (id_rol) DO NOTHING;

        UPDATE usuarios SET id_rol = 'LIDER_PRODUCCION' WHERE id_rol = 'LIDER_MECANIZADOS';

        INSERT INTO rol_permisos (id_rol, id_permiso)
        SELECT 'LIDER_PRODUCCION', id_permiso FROM rol_permisos WHERE id_rol = 'LIDER_MECANIZADOS'
        ON CONFLICT DO NOTHING;
        DELETE FROM rol_permisos WHERE id_rol = 'LIDER_MECANIZADOS';

        IF to_regclass('public.migracion_25_registro') IS NOT NULL THEN
            UPDATE migracion_25_registro SET id_rol = 'LIDER_PRODUCCION' WHERE id_rol = 'LIDER_MECANIZADOS';
        END IF;

        DELETE FROM roles WHERE id_rol = 'LIDER_MECANIZADOS';
    END IF;

    DROP TABLE public.migracion_27_registro;
END $$;

COMMIT;
