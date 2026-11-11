-- 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql
-- SCRUM-27, paso 1b: roles del catálogo de PRISMA (reglas/roles-catalogo.md) y reparto de
-- permisos según reglas/permisos-por-rol-modulo.md.
--   * Crea los roles nuevos que falten. OPERARIO y MANTENIMIENTO pueden existir ya (los crea
--     cargar_semilla.py): si existen no se tocan.
--   * Crea los permisos de aprobación y de consulta restringida que fijan las reglas. Los de
--     crear/editar siguen en los grupos de app/core/roles.py.
--   * Asigna permisos solo a roles del catálogo. Los puntos "Por confirmar" de SCRUM-32 no se
--     asignan.
--   * PERM_OP_LIBERAR queda exclusivamente en LIDER_DISENO y DIBUJANTE: se retira de cualquier
--     otro rol (DISENO lo tenía por la migración 16). Los usuarios con DISENO dejan de liberar
--     OP hasta que se les asigne LIDER_DISENO o DIBUJANTE. ADMIN sigue liberando con
--     PERM_ADMIN_ALL y motivo.
--   * Los usuarios no se reasignan.
--   * Registra en migracion_25_registro lo que inserta y lo que retira, para que la reversión
--     deshaga eso y nada más.
-- Asignaciones:
--   VENTAS              PERM_COTIZACION_EMITIR, PERM_PEDIDO_CONFIRMAR, PERM_RETENCION_GESTIONAR,
--                       PERM_VALOR_COTIZADO_VER (conserva PERM_PROYECTO_CREAR)
--   JEFE_PRODUCCION     PERM_OP_CERRAR, PERM_PEDIDO_CERRAR, PERM_RETENCION_GESTIONAR,
--                       PERM_SOLICITUD_COMPRA_APROBAR, PERM_MANTENIMIENTO_APROBAR,
--                       PERM_VALOR_COTIZADO_VER, PERM_EXPEDIENTE_COSTOS_VER
--   LIDER_DISENO        PERM_OP_LIBERAR, PERM_PLANO_GESTION, PERM_PLANO_APROBAR
--   DIBUJANTE           PERM_OP_LIBERAR, PERM_PLANO_GESTION
--   CALIDAD_PRODUCTO    PERM_CALIDAD_APROBAR
--   GESTION_CALIDAD     PERM_METAS_PROPONER, PERM_VALOR_COTIZADO_VER, PERM_EXPEDIENTE_COSTOS_VER
--   COSTOS              PERM_VALOR_COTIZADO_VER, PERM_EXPEDIENTE_COSTOS_VER
--   GERENCIA            PERM_METAS_APROBAR
--   SECRETARIA_GERENCIA PERM_SOLICITUD_COMPRA_APROBAR (papelería y oficina)
--   LIDER_LOGISTICA     PERM_ORDEN_COMPRA_APROBAR (papelería y oficina)
--   DIRECTOR_PRODUCCION PERM_ORDEN_COMPRA_APROBAR (su cadena), PERM_RETENCION_GESTIONAR
--                       (reglas/retencion-ordenes.md y handoff 2026-11-10)
--   LIDER_PRODUCCION, OPERARIO, MANTENIMIENTO: sin aprobaciones.
-- Idempotente. Lo único que retira (PERM_OP_LIBERAR de otros roles) queda registrado y la
-- reversión lo restaura. NO la ejecuta ningún agente sobre sgi_db: la aplica
-- Dirección con respaldo previo de sgi_db y ensayo en BD de prueba.
-- Requiere 15_MIGRACION_ROL_PERMISOS.sql y los permisos de 02_DATOS_INICIALES.sql (sección 2).
-- Reversión: 25_REVERSION_ROLES_PERMISOS_POR_ROL.sql

BEGIN;

DO $$
DECLARE
    v_faltantes text;
BEGIN
    SELECT string_agg(p, ', ' ORDER BY p) INTO v_faltantes
      FROM unnest(ARRAY['PERM_OP_LIBERAR', 'PERM_PLANO_GESTION', 'PERM_CALIDAD_APROBAR']) AS p
     WHERE NOT EXISTS (SELECT 1 FROM permisos WHERE id_permiso = p);
    IF v_faltantes IS NOT NULL THEN
        RAISE EXCEPTION 'Faltan permisos de 02_DATOS_INICIALES.sql: %', v_faltantes;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM roles WHERE id_rol = 'VENTAS') THEN
        RAISE EXCEPTION 'Falta el rol VENTAS de 02_DATOS_INICIALES.sql.';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS migracion_25_registro (
    tipo VARCHAR(20) NOT NULL,
    id_rol VARCHAR(50),
    id_permiso VARCHAR(100),
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Recrea el CHECK por si la tabla viene de una versión anterior de esta migración
ALTER TABLE migracion_25_registro ALTER COLUMN tipo TYPE VARCHAR(20);
ALTER TABLE migracion_25_registro DROP CONSTRAINT IF EXISTS migracion_25_registro_tipo_check;
ALTER TABLE migracion_25_registro ADD CONSTRAINT migracion_25_registro_tipo_check
    CHECK (tipo IN ('ROL', 'PERMISO', 'ROL_PERMISO', 'ROL_PERMISO_RETIRADO'));
COMMENT ON TABLE migracion_25_registro IS
    'SCRUM-27: filas insertadas o retiradas por 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql; la usa su reversión.';

-- 1. Roles
WITH nuevos AS (
    INSERT INTO roles (id_rol, nombre_rol, descripcion) VALUES
    ('CALIDAD_PRODUCTO', 'Calidad de producto', 'Inspecciones y RNC; aprueba o rechaza producto'),
    ('GESTION_CALIDAD', 'Gestión de Calidad', 'Indicadores, RNC y CAPA, planes de mejora; propone metas'),
    ('JEFE_PRODUCCION', 'Jefe de producción', 'Programa y cierra OP; cierra pedidos; retenciones'),
    ('LIDER_PRODUCCION', 'Líder de producción', 'Avance de operaciones de su área, sin costos'),
    ('OPERARIO', 'Operario', 'Registra avance y tiempos de sus operaciones'),
    ('COSTOS', 'Costos', 'Liquidación de costos y expediente de OP con costos'),
    ('MANTENIMIENTO', 'Mantenimiento', 'Máquinas y órdenes de mantenimiento, sin información de OP'),
    ('LIDER_DISENO', 'Líder de diseño', 'Planos; aprueba planos; libera OP'),
    ('DIBUJANTE', 'Dibujante', 'Planos asignados, sin aprobar; libera OP'),
    ('GERENCIA', 'Gerencia', 'Tablero de Dirección; aprueba metas y planes de mejora'),
    ('SECRETARIA_GERENCIA', 'Secretaria de gerencia', 'Aprueba solicitudes de papelería y oficina'),
    ('LIDER_LOGISTICA', 'Líder de logística', 'Picking y despacho; aprueba órdenes de papelería y oficina'),
    ('DIRECTOR_PRODUCCION', 'Director de producción', 'Aprueba órdenes de compra de su cadena; retenciones')
    ON CONFLICT (id_rol) DO NOTHING
    RETURNING id_rol
)
INSERT INTO migracion_25_registro (tipo, id_rol)
SELECT 'ROL', id_rol FROM nuevos;

-- 2. Permisos
WITH nuevos AS (
    INSERT INTO permisos (id_permiso, modulo, descripcion) VALUES
    ('PERM_COTIZACION_EMITIR', 'VENTAS', 'Emitir cotizaciones'),
    ('PERM_PEDIDO_CONFIRMAR', 'VENTAS', 'Confirmar pedido desde cotización (RN-VEN-003)'),
    ('PERM_RETENCION_GESTIONAR', 'VENTAS', 'Retener pedidos y OP y levantar la retención'),
    ('PERM_VALOR_COTIZADO_VER', 'VENTAS', 'Ver el valor cotizado'),
    ('PERM_OP_CERRAR', 'PRODUCCION', 'Cerrar Orden de Producción'),
    ('PERM_PEDIDO_CERRAR', 'PRODUCCION', 'Cerrar pedido (acción manual)'),
    ('PERM_EXPEDIENTE_COSTOS_VER', 'COSTOS', 'Ver costos directos e indirectos en el expediente de OP'),
    ('PERM_PLANO_APROBAR', 'DISENO', 'Aprobar planos'),
    ('PERM_SOLICITUD_COMPRA_APROBAR', 'COMPRAS', 'Aprobar solicitudes de compra de su cadena'),
    ('PERM_ORDEN_COMPRA_APROBAR', 'COMPRAS', 'Aprobar órdenes de compra de su cadena'),
    ('PERM_MANTENIMIENTO_APROBAR', 'MANTENIMIENTO', 'Aprobar solicitudes de mantenimiento'),
    ('PERM_METAS_PROPONER', 'CALIDAD', 'Proponer metas de KPI y planes de mejora'),
    ('PERM_METAS_APROBAR', 'GERENCIA', 'Aprobar metas de KPI y planes de mejora')
    ON CONFLICT (id_permiso) DO NOTHING
    RETURNING id_permiso
)
INSERT INTO migracion_25_registro (tipo, id_permiso)
SELECT 'PERMISO', id_permiso FROM nuevos;

-- 3. Asignaciones
WITH nuevas AS (
    INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
    ('VENTAS', 'PERM_COTIZACION_EMITIR'),
    ('VENTAS', 'PERM_PEDIDO_CONFIRMAR'),
    ('VENTAS', 'PERM_RETENCION_GESTIONAR'),
    ('VENTAS', 'PERM_VALOR_COTIZADO_VER'),
    ('JEFE_PRODUCCION', 'PERM_OP_CERRAR'),
    ('JEFE_PRODUCCION', 'PERM_PEDIDO_CERRAR'),
    ('JEFE_PRODUCCION', 'PERM_RETENCION_GESTIONAR'),
    ('JEFE_PRODUCCION', 'PERM_SOLICITUD_COMPRA_APROBAR'),
    ('JEFE_PRODUCCION', 'PERM_MANTENIMIENTO_APROBAR'),
    ('JEFE_PRODUCCION', 'PERM_VALOR_COTIZADO_VER'),
    ('JEFE_PRODUCCION', 'PERM_EXPEDIENTE_COSTOS_VER'),
    ('LIDER_DISENO', 'PERM_OP_LIBERAR'),
    ('LIDER_DISENO', 'PERM_PLANO_GESTION'),
    ('LIDER_DISENO', 'PERM_PLANO_APROBAR'),
    ('DIBUJANTE', 'PERM_OP_LIBERAR'),
    ('DIBUJANTE', 'PERM_PLANO_GESTION'),
    ('CALIDAD_PRODUCTO', 'PERM_CALIDAD_APROBAR'),
    ('GESTION_CALIDAD', 'PERM_METAS_PROPONER'),
    ('GESTION_CALIDAD', 'PERM_VALOR_COTIZADO_VER'),
    ('GESTION_CALIDAD', 'PERM_EXPEDIENTE_COSTOS_VER'),
    ('COSTOS', 'PERM_VALOR_COTIZADO_VER'),
    ('COSTOS', 'PERM_EXPEDIENTE_COSTOS_VER'),
    ('GERENCIA', 'PERM_METAS_APROBAR'),
    ('SECRETARIA_GERENCIA', 'PERM_SOLICITUD_COMPRA_APROBAR'),
    ('LIDER_LOGISTICA', 'PERM_ORDEN_COMPRA_APROBAR'),
    ('DIRECTOR_PRODUCCION', 'PERM_ORDEN_COMPRA_APROBAR'),
    ('DIRECTOR_PRODUCCION', 'PERM_RETENCION_GESTIONAR')
    ON CONFLICT DO NOTHING
    RETURNING id_rol, id_permiso
)
INSERT INTO migracion_25_registro (tipo, id_rol, id_permiso)
SELECT 'ROL_PERMISO', id_rol, id_permiso FROM nuevas;

-- 4. PERM_OP_LIBERAR exclusivo de LIDER_DISENO y DIBUJANTE
-- Si la fila retirada la había insertado esta migración (versión anterior), se quita su
-- registro en vez de anotarla como retirada: la reversión no debe restaurarla.
WITH retiradas AS (
    DELETE FROM rol_permisos
     WHERE id_permiso = 'PERM_OP_LIBERAR'
       AND id_rol NOT IN ('LIDER_DISENO', 'DIBUJANTE')
    RETURNING id_rol, id_permiso
), propias AS (
    DELETE FROM migracion_25_registro r
     USING retiradas x
     WHERE r.tipo = 'ROL_PERMISO' AND r.id_rol = x.id_rol AND r.id_permiso = x.id_permiso
    RETURNING r.id_rol, r.id_permiso
)
INSERT INTO migracion_25_registro (tipo, id_rol, id_permiso)
SELECT 'ROL_PERMISO_RETIRADO', x.id_rol, x.id_permiso
  FROM retiradas x
 WHERE NOT EXISTS (SELECT 1 FROM propias p WHERE p.id_rol = x.id_rol AND p.id_permiso = x.id_permiso);

COMMIT;
