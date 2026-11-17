-- 34_REVERSION_ACCESO_POR_USUARIO.sql
-- Reversión de 34_MIGRACION_ACCESO_POR_USUARIO.sql: vuelve a hacer obligatorio usuarios.email,
-- elimina usuarios.usuario y usuarios_historial.
--   * Se detiene SIN cambiar nada si algún usuario no tiene correo (no podría volver a entrar) o
--     si hay filas en usuarios_historial (son auditoría): lista los casos.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DO $$
DECLARE
    v_sin_correo text;
    v_historial bigint := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'usuarios' AND column_name = 'usuario') THEN
        EXECUTE 'SELECT string_agg(usuario, '', '' ORDER BY usuario) FROM usuarios WHERE email IS NULL'
           INTO v_sin_correo;
    END IF;
    IF v_sin_correo IS NOT NULL THEN
        RAISE EXCEPTION 'Usuarios sin correo; asígneles uno antes de revertir: %', v_sin_correo;
    END IF;
    IF to_regclass('public.usuarios_historial') IS NOT NULL THEN
        SELECT count(*) INTO v_historial FROM usuarios_historial;
    END IF;
    IF v_historial > 0 THEN
        RAISE EXCEPTION 'Hay % cambio(s) de cuentas en usuarios_historial; respáldelos y vacíe la tabla antes de revertir.', v_historial;
    END IF;
END $$;

DROP TABLE IF EXISTS usuarios_historial;
ALTER TABLE usuarios ALTER COLUMN email SET NOT NULL;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS ck_usuarios_usuario_formato;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS uq_usuarios_usuario;
ALTER TABLE usuarios DROP COLUMN IF EXISTS usuario;

COMMIT;
