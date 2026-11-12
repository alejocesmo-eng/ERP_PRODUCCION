-- 27_MIGRACION_ROL_LIDER_MECANIZADOS.sql
-- Renombra el rol LIDER_PRODUCCION (migración 25) a LIDER_MECANIZADOS, "Líder de Mecanizados"
-- (reglas/permisos-por-rol-modulo.md y reglas/roles-catalogo.md del proyecto PRISMA).
--   * roles.id_rol no tiene ON UPDATE CASCADE: se crea LIDER_MECANIZADOS, se pasan a él los
--     usuarios y las asignaciones de LIDER_PRODUCCION y se borra LIDER_PRODUCCION.
--   * migracion_25_registro pasa a nombrar LIDER_MECANIZADOS, para que la guarda de la reversión
--     25 siga viendo a sus usuarios.
--   * Asigna PERM_OP_CERRAR: cierra OP de cualquier unidad como respaldo del Jefe de Producción.
--     No recibe PERM_OP_LIBERAR, PERM_RETENCION_GESTIONAR, PERM_VALOR_COTIZADO_VER ni
--     PERM_EXPEDIENTE_COSTOS_VER.
--   * Registra en migracion_27_registro el renombre y la asignación nueva, para que la
--     reversión deshaga eso y nada más.
-- Idempotente: si LIDER_PRODUCCION reaparece (por ejemplo, al volver a aplicar la 25), sus
-- usuarios y asignaciones pasan otra vez a LIDER_MECANIZADOS.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Requiere 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql.
-- Reversión: 27_REVERSION_ROL_LIDER_MECANIZADOS.sql

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM roles WHERE id_rol IN ('LIDER_PRODUCCION', 'LIDER_MECANIZADOS')) THEN
        RAISE EXCEPTION 'No existe LIDER_PRODUCCION ni LIDER_MECANIZADOS: aplique antes la migración 25.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM permisos WHERE id_permiso = 'PERM_OP_CERRAR') THEN
        RAISE EXCEPTION 'Falta el permiso PERM_OP_CERRAR de la migración 25.';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS migracion_27_registro (
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('ROL_RENOMBRADO', 'ROL_PERMISO')),
    id_rol VARCHAR(50),
    id_permiso VARCHAR(100),
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE migracion_27_registro IS
    'Renombre de LIDER_PRODUCCION a LIDER_MECANIZADOS (27_MIGRACION_ROL_LIDER_MECANIZADOS.sql); la usa su reversión.';

-- 1. Rol nuevo (si LIDER_PRODUCCION existe y LIDER_MECANIZADOS no, es un renombre)
WITH nuevo AS (
    INSERT INTO roles (id_rol, nombre_rol, descripcion)
    SELECT 'LIDER_MECANIZADOS', 'Líder de Mecanizados',
           'Asigna operarios, secuencia y estaciones; cierra OP como respaldo; sin costos'
     WHERE EXISTS (SELECT 1 FROM roles WHERE id_rol = 'LIDER_PRODUCCION')
    ON CONFLICT (id_rol) DO NOTHING
    RETURNING id_rol
)
INSERT INTO migracion_27_registro (tipo, id_rol)
SELECT 'ROL_RENOMBRADO', id_rol FROM nuevo;

UPDATE roles
   SET nombre_rol = 'Líder de Mecanizados',
       descripcion = 'Asigna operarios, secuencia y estaciones; cierra OP como respaldo; sin costos'
 WHERE id_rol = 'LIDER_MECANIZADOS';

-- 2. Usuarios y asignaciones de LIDER_PRODUCCION pasan a LIDER_MECANIZADOS
UPDATE usuarios SET id_rol = 'LIDER_MECANIZADOS' WHERE id_rol = 'LIDER_PRODUCCION';

INSERT INTO rol_permisos (id_rol, id_permiso)
SELECT 'LIDER_MECANIZADOS', id_permiso FROM rol_permisos WHERE id_rol = 'LIDER_PRODUCCION'
ON CONFLICT DO NOTHING;
DELETE FROM rol_permisos WHERE id_rol = 'LIDER_PRODUCCION';

-- 3. Registro de la 25: sin filas repetidas
DO $$
BEGIN
    IF to_regclass('public.migracion_25_registro') IS NOT NULL THEN
        DELETE FROM migracion_25_registro v
         WHERE v.id_rol = 'LIDER_PRODUCCION'
           AND EXISTS (
                SELECT 1 FROM migracion_25_registro n
                 WHERE n.id_rol = 'LIDER_MECANIZADOS' AND n.tipo = v.tipo
                   AND n.id_permiso IS NOT DISTINCT FROM v.id_permiso
           );
        UPDATE migracion_25_registro SET id_rol = 'LIDER_MECANIZADOS' WHERE id_rol = 'LIDER_PRODUCCION';
    END IF;
END $$;

DELETE FROM roles WHERE id_rol = 'LIDER_PRODUCCION';

-- 4. Cierre de OP como respaldo del Jefe de Producción
WITH nuevas AS (
    INSERT INTO rol_permisos (id_rol, id_permiso) VALUES ('LIDER_MECANIZADOS', 'PERM_OP_CERRAR')
    ON CONFLICT DO NOTHING
    RETURNING id_rol, id_permiso
)
INSERT INTO migracion_27_registro (tipo, id_rol, id_permiso)
SELECT 'ROL_PERMISO', id_rol, id_permiso FROM nuevas;

COMMIT;
