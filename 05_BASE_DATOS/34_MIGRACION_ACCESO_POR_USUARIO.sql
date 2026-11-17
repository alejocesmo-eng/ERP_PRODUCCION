-- 34_MIGRACION_ACCESO_POR_USUARIO.sql
-- Inicio de sesión por usuario (reglas/acceso-por-usuario.md del proyecto PRISMA).
--   * usuarios.usuario: único, obligatorio, de 3 a 50 caracteres con minúsculas, números, punto,
--     guion bajo y guion (sin espacios ni tildes). Es lo único con que se entra.
--   * usuarios.email deja de ser obligatorio; sigue único cuando tiene valor.
--   * Cuentas existentes: usuario = parte del correo antes de la @, en minúsculas y sin tildes.
--     Si dos cuentas darían el mismo usuario, o el resultado no cumple el formato, se detiene SIN
--     cambiar nada y lista los casos.
--   * usuarios_historial: cada alta, edición, cambio de rol, asignación de contraseña,
--     desactivación y reactivación hecha desde Configuración, con el identificador interno de
--     quien la hizo. Solo se agregan filas.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Reversión: 34_REVERSION_ACCESO_POR_USUARIO.sql

BEGIN;

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS usuario VARCHAR(50);

DO $$
DECLARE
    v_casos text;
BEGIN
    -- Candidato de cada cuenta sin usuario, y de las que ya lo tienen (para detectar choques)
    CREATE TEMP TABLE m34_candidatos ON COMMIT DROP AS
    SELECT id_usuario, email,
           COALESCE(usuario, translate(lower(split_part(btrim(email), '@', 1)),
                                       'áàäâãéèëêíìïîóòöôõúùüûñç', 'aaaaaeeeeiiiiooooouuuunc')) AS candidato,
           usuario IS NULL AS nuevo
      FROM usuarios;

    SELECT string_agg(format('%s -> "%s" (formato inválido)', COALESCE(email, id_usuario::text), candidato), '; '
                      ORDER BY email)
      INTO v_casos
      FROM m34_candidatos
     WHERE nuevo AND (candidato IS NULL OR candidato !~ '^[a-z0-9._-]{3,50}$');
    IF v_casos IS NOT NULL THEN
        RAISE EXCEPTION 'Cuentas cuyo usuario no se puede deducir del correo; asígnelo a mano antes de migrar: %', v_casos;
    END IF;

    SELECT string_agg(format('"%s": %s', candidato, correos), '; ' ORDER BY candidato)
      INTO v_casos
      FROM (SELECT candidato, string_agg(COALESCE(email, id_usuario::text), ', ' ORDER BY email) AS correos
              FROM m34_candidatos GROUP BY candidato HAVING count(*) > 1) repetidos;
    IF v_casos IS NOT NULL THEN
        RAISE EXCEPTION 'Cuentas que darían el mismo usuario; asígneles uno distinto antes de migrar: %', v_casos;
    END IF;

    UPDATE usuarios u SET usuario = c.candidato
      FROM m34_candidatos c
     WHERE c.id_usuario = u.id_usuario AND c.nuevo;
END $$;

ALTER TABLE usuarios ALTER COLUMN usuario SET NOT NULL;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS uq_usuarios_usuario;
ALTER TABLE usuarios ADD CONSTRAINT uq_usuarios_usuario UNIQUE (usuario);
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS ck_usuarios_usuario_formato;
ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_usuario_formato CHECK (usuario ~ '^[a-z0-9._-]{3,50}$');
ALTER TABLE usuarios ALTER COLUMN email DROP NOT NULL;
COMMENT ON COLUMN usuarios.usuario IS
    'Con lo que se entra: 3 a 50 caracteres, minúsculas, números, punto, guion bajo y guion.';
COMMENT ON COLUMN usuarios.email IS 'Dato de contacto opcional; único cuando tiene valor. No sirve para entrar.';

CREATE TABLE IF NOT EXISTS usuarios_historial (
    id_historial BIGSERIAL PRIMARY KEY,
    id_usuario UUID NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    accion VARCHAR(30) NOT NULL CHECK (accion IN (
        'CREADO', 'EDITADO', 'ROL_ASIGNADO', 'CLAVE_ASIGNADA', 'DESACTIVADO', 'REACTIVADO'
    )),
    cambios JSONB NOT NULL DEFAULT '{}'::jsonb,
    realizado_por VARCHAR(100) NOT NULL,
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_usuarios_historial_usuario ON usuarios_historial (id_usuario);
COMMENT ON TABLE usuarios_historial IS
    'Cambios de cuentas hechos desde Configuración. realizado_por es el id_usuario de quien los hizo; '
    'cambios nunca guarda contraseñas.';

COMMIT;
