-- 30_REVERSION_TIEMPOS_LIDER_MECANIZADOS.sql
-- Reversión de 30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql: quita PERM_TIEMPOS_REGISTRAR de
-- LIDER_MECANIZADOS solo si lo asignó la migración (migracion_30_registro) y elimina esa tabla.
-- Revierta la 30 antes que la 29 y la 27. Idempotente. Solo con autorización de Dirección y
-- respaldo previo. NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.migracion_30_registro') IS NULL THEN
        RAISE NOTICE 'No existe migracion_30_registro: la migración 30 no está aplicada.';
        RETURN;
    END IF;

    DELETE FROM rol_permisos rp
     USING migracion_30_registro r
     WHERE r.id_rol = rp.id_rol AND r.id_permiso = rp.id_permiso;

    DROP TABLE public.migracion_30_registro;
END $$;

COMMIT;
